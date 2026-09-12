const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { window, ok, eq, arrEq } = api;
  const D = window.__dim;
  console.log("\n[dim-convert 纯函数]");

  ok("__dim 已导出", !!D && typeof D.rotPt === "function");

  // norm3 单位化
  arrEq(D.norm3([3,0,0]), [1,0,0], "norm3 X轴");
  arrEq(D.norm3([0,0,-5]), [0,0,-1], "norm3 -Z轴");

  // rotPt：绕 Y 轴 +90° → (1,0,0) 变 (0,0,-1)（浮点容差）
  (function(){
    const r = D.rotPt([1,0,0], Math.PI/2, 0);
    const got = r.map(x=>Math.abs(x) < 1e-9 ? 0 : x);
    arrEq(got, [0,0,-1], "rotPt Y+90");
  })();
  // rotPt：绕 X 轴 +90° → (0,0,1) 变 (0,-1,0)（浮点容差）
  (function(){
    const r = D.rotPt([0,0,1], 0, Math.PI/2);
    const got = r.map(x=>Math.abs(x) < 1e-9 ? 0 : x);
    arrEq(got, [0,-1,0], "rotPt X+90");
  })();

  // triNormal：XY 平面三角形法线指向 +Z
  arrEq(D.triNormal([0,0,0],[1,0,0],[0,1,0]), [0,0,1], "triNormal +Z");

  // solve3：单位矩阵解 [5,6,7]
  arrEq(D.solve3([[1,0,0],[0,1,0],[0,0,1]], [5,6,7]), [5,6,7], "solve3 单位阵");

  // buildOBJ：3x3 掩码仅中心像素 → 应有顶点与面
  const g = 3, mask = new Uint8Array(9); mask[4] = 1;
  const txt = D.buildOBJ(g, mask, 30, 30, 0.1, 0.4);
  const lines = txt.split("\n");
  const vLines = lines.filter(l => l.charAt(0) === "v").length;
  const fLines = lines.filter(l => l.charAt(0) === "f").length;
  ok("buildOBJ 含注释头", txt.indexOf("extruded silhouette") >= 0);
  ok("buildOBJ 顶点数>0 ("+vLines+")", vLines > 0);
  ok("buildOBJ 面数>0 ("+fLines+")", fLines > 0);
  // 每个面行应为 "f a b c"（三角化）
  const badF = lines.filter(l => l.charAt(0)==="f").some(l => l.trim().split(/\s+/).length !== 4);
  ok("buildOBJ 面均为三角面", !badF);

  // 全空掩码应产出 0 顶点
  const empty = D.buildOBJ(g, new Uint8Array(9), 30, 30, 0.1, 0.4);
  eq(empty.split("\n").filter(l => l.charAt(0)==="v").length, 0, "空掩码无顶点");
});
