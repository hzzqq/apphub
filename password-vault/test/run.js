// password-vault 加密算法验证：PBKDF2(SHA-256,100k) + AES-GCM(256)
// 复刻 index.html 中的 encryptItems/decryptItems 参数与格式，验证可解密 + 错误密码失败。
const { webcrypto } = require("crypto");
const crypto = webcrypto;
function b64(buf){ return Buffer.from(buf).toString("base64"); }
function unb64(s){ return new Uint8Array(Buffer.from(s, "base64")); }
async function deriveKey(master, salt){
  const enc = new TextEncoder();
  const km = await crypto.subtle.importKey("raw", enc.encode(master), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name:"PBKDF2", salt:salt, iterations:100000, hash:"SHA-256" }, km, { name:"AES-GCM", length:256 }, false, ["encrypt","decrypt"]);
}
async function enc(master, obj, salt){
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(master, salt);
  const ct = await crypto.subtle.encrypt({ name:"AES-GCM", iv:iv }, key, new TextEncoder().encode(JSON.stringify(obj)));
  return b64(iv) + ":" + b64(ct);
}
async function dec(master, stored, salt){
  const parts = stored.split(":");
  const key = await deriveKey(master, salt);
  const pt = await crypto.subtle.decrypt({ name:"AES-GCM", iv:unb64(parts[0]) }, key, unb64(parts[1]));
  return JSON.parse(new TextDecoder().decode(pt));
}
(async () => {
  let pass = 0, fail = 0;
  const ok = (c, m) => { if (c) { pass++; } else { fail++; console.log("FAIL:", m); } };
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const obj = [{ site:"github.com", user:"boss", pass:"p@ssw0rd!23" }, { site:"bank", user:"hz", pass:"x" }];
  const s = await enc("master123", obj, salt);
  const d = await dec("master123", s, salt);
  ok(JSON.stringify(d) === JSON.stringify(obj), "round-trip decrypt matches original");
  let threw = false;
  try { await dec("wrong-password", s, salt); } catch (e) { threw = true; }
  ok(threw, "wrong master password fails to decrypt (AES-GCM auth tag)");
  ok(s.includes(":"), "stored format is iv:ct base64");
  console.log(`password-vault crypto: ${pass} passed / ${fail} failed`);
  if (fail) process.exit(1);
})();
