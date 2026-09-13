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

  // parseGLB：构造最小 GLB（单三角、非索引）验证解析
  (function(){
    function makeGLB(jsonObj, bin){
      const enc = new TextEncoder();
      let json = JSON.stringify(jsonObj);
      while(json.length % 4 !== 0) json += " ";
      const jb = enc.encode(json);
      const total = 12 + 8 + jb.length + 8 + bin.length;
      const buf = new ArrayBuffer(total);
      const dv = new DataView(buf);
      dv.setUint32(0, 0x46546C67, true); // 'glTF'
      dv.setUint32(4, 2, true);
      dv.setUint32(8, total, true);
      dv.setUint32(12, jb.length, true);
      dv.setUint32(16, 0x4E4F534A, true); // 'JSON'
      new Uint8Array(buf, 20, jb.length).set(jb);
      const binOff = 20 + jb.length;
      dv.setUint32(binOff, bin.length, true);
      dv.setUint32(binOff + 4, 0x004E4942, true); // 'BIN\0'
      new Uint8Array(buf, binOff + 8, bin.length).set(bin);
      return buf;
    }
    const verts = new Float32Array([1,0,0, 0,1,0, 0,0,1]);
    const bin = new Uint8Array(verts.buffer);
    const glb = makeGLB({
      buffers:[{byteLength: bin.length}],
      bufferViews:[{buffer:0, byteOffset:0, byteLength: bin.length}],
      accessors:[{bufferView:0, componentType:5126, count:3, type:"VEC3"}],
      meshes:[{primitives:[{attributes:{POSITION:0}}]}]
    }, bin);
    const res = D.parseGLB(glb);
    ok("parseGLB 返回非 null", !!res);
    ok("parseGLB 顶点数=3", res && res.vertices.length === 3);
    if(res){
      const v0 = res.vertices[0].map(x => Math.abs(x) < 1e-6 ? 0 : x);
      arrEq(v0, [1,0,0], "parseGLB 顶点0 = (1,0,0)");
      eq(res.triangles.length, 1, "parseGLB 三角数=1");
      arrEq(res.triangles[0], [0,1,2], "parseGLB 非索引三角 [0,1,2]");
    }
    // 非 GLB 数据应返回 null（防误判）
    eq(D.parseGLB(new Uint8Array([1,2,3,4]).buffer), null, "parseGLB 非GLB→null");
  })();

  // shadeColor：真 3D 预览双色调着色，返回合法 RGB
  (function(){
    const L = D.norm3([-0.4, 0.6, 0.7]);  // 与代码内 lightDir 一致
    const lit = D.shadeColor(L);           // 正对光源：漫反射最强
    const cam = D.shadeColor([0, 0, 1]);  // 正对相机
    const side = D.shadeColor([1, 0, 0]);  // 侧向：边缘光最强
    ok("shadeColor 返回 3 元素", Array.isArray(lit) && lit.length === 3);
    ok("shadeColor 通道 ∈ [0,255]",
       lit.every(v => v >= 0 && v <= 255) && side.every(v => v >= 0 && v <= 255));
    ok("正对光源比正对相机更亮(漫反射主导)", lit[0] > cam[0]);
    ok("侧向法线边缘光更强(蓝通道更高)", side[2] > cam[2]);
    ok("shadeColor 确定性(同输入同输出)",
       JSON.stringify(D.shadeColor(L)) === JSON.stringify(D.shadeColor(L)));
  })();
});
