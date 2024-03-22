let a2 = `string`,
  $ = 0,
  a1 = `function`,
  W = null,
  Z = `utf-8`,
  a5 = 16,
  aa = 82,
  a3 = `Object`,
  Y = `undefined`,
  X = 1,
  a6 = 4,
  U = Array,
  _ = Error,
  a4 = FinalizationRegistry,
  a8 = Object,
  a9 = Promise,
  a7 = Reflect,
  a0 = Uint8Array,
  V = undefined;
var r = () => {
  if (q === W || q.byteLength === $) {
    q = new Int32Array(a.memory.buffer);
  }
  return q;
};
var f = (a) => {
  const b = c(a);
  e(a);
  return b;
};
var z = (b, c, d) => {
  a._dyn_core__ops__function__FnMut__A____Output___R_as_wasm_bindgen__closure__WasmClosure___describe__invoke__hbfb83dedd747153b(
    b,
    c,
    g(d),
  );
};
var O = async (a, b) => {
  if (typeof Response === a1 && a instanceof Response) {
    if (typeof WebAssembly.instantiateStreaming === a1) {
      try {
        return await WebAssembly.instantiateStreaming(a, b);
      } catch (b) {
        if (a.headers.get(`Content-Type`) != `application/wasm`) {
          console.warn(
            `\`WebAssembly.instantiateStreaming\` failed because your server does not serve wasm with \`application/wasm\` MIME type. Falling back to \`WebAssembly.instantiate\` which is slower. Original error:\\n`,
            b,
          );
        } else {
          throw b;
        }
      }
    }
    const c = await a.arrayBuffer();
    return await WebAssembly.instantiate(c, b);
  } else {
    const c = await WebAssembly.instantiate(a, b);
    if (c instanceof WebAssembly.Instance) {
      return { instance: c, module: a };
    } else {
      return c;
    }
  }
};
var c = (a) => b[a];
var H = (b, c, d, e) => {
  a.wasm_bindgen__convert__closures__invoke2_mut__h80139da9458afb4e(
    b,
    c,
    g(d),
    g(e),
  );
};
var o = (a, b, c) => {
  if (c === V) {
    const c = m.encode(a);
    const d = b(c.length, X) >>> $;
    j()
      .subarray(d, d + c.length)
      .set(c);
    l = c.length;
    return d;
  }
  let d = a.length;
  let e = b(d, X) >>> $;
  const f = j();
  let g = $;
  for (; g < d; g++) {
    const b = a.charCodeAt(g);
    if (b > 127) break;
    f[e + g] = b;
  }
  if (g !== d) {
    if (g !== $) {
      a = a.slice(g);
    }
    e = c(e, d, (d = g + a.length * 3), X) >>> $;
    const b = j().subarray(e + g, e + d);
    const f = n(a, b);
    g += f.written;
    e = c(e, d, g, X) >>> $;
  }
  l = g;
  return e;
};
function G(b, c) {
  try {
    return b.apply(this, c);
  } catch (b) {
    a.__wbindgen_exn_store(g(b));
  }
}
var w = (b, c, d, e) => {
  const f = { a: b, b: c, cnt: X, dtor: d };
  const g = (...b) => {
    f.cnt++;
    try {
      return e(f.a, f.b, ...b);
    } finally {
      if (--f.cnt === $) {
        a.__wbindgen_export_2.get(f.dtor)(f.a, f.b);
        f.a = $;
        t.unregister(f);
      }
    }
  };
  g.original = f;
  t.register(g, f, f);
  return g;
};
var e = (a) => {
  if (a < 132) return;
  b[a] = d;
  d = a;
};
var C = (a) => () => {
  throw new _(`${a} is not defined`);
};
var B = (a, b) => {
  if (a === $) {
    return c(b);
  } else {
    return k(a, b);
  }
};
var x = (b, c, d) => {
  a.wasm_bindgen__convert__closures__invoke1__h3587d13b177f4310(b, c, g(d));
};
var S = (b) => {
  if (a !== V) return a;
  const c = P();
  Q(c);
  if (!(b instanceof WebAssembly.Module)) {
    b = new WebAssembly.Module(b);
  }
  const d = new WebAssembly.Instance(b, c);
  return R(d, b);
};
var g = (a) => {
  if (d === b.length) b.push(b.length + X);
  const c = d;
  d = b[c];
  b[c] = a;
  return c;
};
var v = (b, c) => {
  a.wasm_bindgen__convert__closures__invoke0_mut__h4a24e1d3a939eab3(b, c);
};
var Q = (a, b) => {};
var k = (a, b) => {
  a = a >>> $;
  return h.decode(j().subarray(a, a + b));
};
var y = (b, c, d) => {
  a.wasm_bindgen__convert__closures__invoke1_mut__hb3e9c01e72342709(b, c, g(d));
};
var j = () => {
  if (i === W || i.byteLength === $) {
    i = new a0(a.memory.buffer);
  }
  return i;
};
var R = (b, c) => {
  a = b.exports;
  T.__wbindgen_wasm_module = c;
  q = W;
  i = W;
  a.__wbindgen_start();
  return a;
};
var u = (b, c, d, e) => {
  const f = { a: b, b: c, cnt: X, dtor: d };
  const g = (...b) => {
    f.cnt++;
    const c = f.a;
    f.a = $;
    try {
      return e(c, f.b, ...b);
    } finally {
      if (--f.cnt === $) {
        a.__wbindgen_export_2.get(f.dtor)(c, f.b);
        t.unregister(f);
      } else {
        f.a = c;
      }
    }
  };
  g.original = f;
  t.register(g, f, f);
  return g;
};
var s = (a) => {
  const b = typeof a;
  if (b == `number` || b == `boolean` || a == W) {
    return `${a}`;
  }
  if (b == a2) {
    return `"${a}"`;
  }
  if (b == `symbol`) {
    const b = a.description;
    if (b == W) {
      return `Symbol`;
    } else {
      return `Symbol(${b})`;
    }
  }
  if (b == a1) {
    const b = a.name;
    if (typeof b == a2 && b.length > $) {
      return `Function(${b})`;
    } else {
      return `Function`;
    }
  }
  if (U.isArray(a)) {
    const b = a.length;
    let c = `[`;
    if (b > $) {
      c += s(a[$]);
    }
    for (let d = X; d < b; d++) {
      c += `, ` + s(a[d]);
    }
    c += `]`;
    return c;
  }
  const c = /\[object ([^\]]+)\]/.exec(toString.call(a));
  let d;
  if (c.length > X) {
    d = c[X];
  } else {
    return toString.call(a);
  }
  if (d == a3) {
    try {
      return `Object(` + JSON.stringify(a) + `)`;
    } catch (a) {
      return a3;
    }
  }
  if (a instanceof _) {
    return `${a.name}: ${a.message}\n${a.stack}`;
  }
  return d;
};
var p = (a) => a === V || a === W;
var T = async (b) => {
  if (a !== V) return a;
  if (typeof b === Y) {
    b = new URL(`schemedit_bg.wasm`, import.meta.url);
  }
  const c = P();
  if (
    typeof b === a2 ||
    (typeof Request === a1 && b instanceof Request) ||
    (typeof URL === a1 && b instanceof URL)
  ) {
    b = fetch(b);
  }
  Q(c);
  const { instance: d, module: e } = await O(await b, c);
  return R(d, e);
};
var P = () => {
  const b = {};
  b.wbg = {};
  b.wbg.__wbindgen_object_drop_ref = (a) => {
    f(a);
  };
  b.wbg.__wbindgen_object_clone_ref = (a) => {
    const b = c(a);
    return g(b);
  };
  b.wbg.__wbindgen_cb_drop = (a) => {
    const b = f(a).original;
    if (b.cnt-- == X) {
      b.a = $;
      return !0;
    }
    const c = !1;
    return c;
  };
  b.wbg.__wbindgen_string_new = (a, b) => {
    const c = k(a, b);
    return g(c);
  };
  b.wbg.__wbg_new_abda76e883ba8a5f = () => {
    const a = new _();
    return g(a);
  };
  b.wbg.__wbg_stack_658279fe44541cf6 = (b, d) => {
    const e = c(d).stack;
    const f = o(e, a.__wbindgen_malloc, a.__wbindgen_realloc);
    const g = l;
    r()[b / a6 + X] = g;
    r()[b / a6 + $] = f;
  };
  b.wbg.__wbg_error_f851667af71bcfc6 = (b, c) => {
    var d = B(b, c);
    if (b !== $) {
      a.__wbindgen_free(b, c, X);
    }
    console.error(d);
  };
  b.wbg.__wbg_getThemeFromLocalStorage_b90b38b41a06a6eb =
    typeof getThemeFromLocalStorage == a1
      ? getThemeFromLocalStorage
      : C(`getThemeFromLocalStorage`);
  b.wbg.__wbg_postParent_8f2bebb355bda272 = (a, b) => {
    var c = B(a, b);
    postParent(c);
  };
  b.wbg.__wbindgen_string_get = (b, d) => {
    const e = c(d);
    const f = typeof e === a2 ? e : V;
    var g = p(f) ? $ : o(f, a.__wbindgen_malloc, a.__wbindgen_realloc);
    var h = l;
    r()[b / a6 + X] = h;
    r()[b / a6 + $] = g;
  };
  b.wbg.__wbg_reloadLayout_a6ed39d880cb1586 =
    typeof reloadLayout == a1 ? reloadLayout : C(`reloadLayout`);
  b.wbg.__wbindgen_is_undefined = (a) => {
    const b = c(a) === V;
    return b;
  };
  b.wbg.__wbg_instanceof_Window_f401953a2cf86220 = (a) => {
    let b;
    try {
      b = c(a) instanceof Window;
    } catch (a) {
      b = !1;
    }
    const d = b;
    return d;
  };
  b.wbg.__wbg_document_5100775d18896c16 = (a) => {
    const b = c(a).document;
    return p(b) ? $ : g(b);
  };
  b.wbg.__wbg_prompt_64ae928b182370a7 = function () {
    return G((b, d, e, f, g, h) => {
      var i = B(e, f);
      var j = B(g, h);
      const k = c(d).prompt(i, j);
      var m = p(k) ? $ : o(k, a.__wbindgen_malloc, a.__wbindgen_realloc);
      var n = l;
      r()[b / a6 + X] = n;
      r()[b / a6 + $] = m;
    }, arguments);
  };
  b.wbg.__wbg_createElement_8bae7856a4bb7411 = function () {
    return G((a, b, d) => {
      var e = B(b, d);
      const f = c(a).createElement(e);
      return g(f);
    }, arguments);
  };
  b.wbg.__wbg_getElementById_c369ff43f0db99cf = (a, b, d) => {
    var e = B(b, d);
    const f = c(a).getElementById(e);
    return p(f) ? $ : g(f);
  };
  b.wbg.__wbg_setinnerHTML_26d69b59e1af99c7 = (a, b, d) => {
    var e = B(b, d);
    c(a).innerHTML = e;
  };
  b.wbg.__wbg_removeAttribute_1b10a06ae98ebbd1 = function () {
    return G((a, b, d) => {
      var e = B(b, d);
      c(a).removeAttribute(e);
    }, arguments);
  };
  b.wbg.__wbg_setAttribute_3c9f6c303b696daa = function () {
    return G((a, b, d, e, f) => {
      var g = B(b, d);
      var h = B(e, f);
      c(a).setAttribute(g, h);
    }, arguments);
  };
  b.wbg.__wbg_getContext_df50fa48a8876636 = function () {
    return G((a, b, d) => {
      var e = B(b, d);
      const f = c(a).getContext(e);
      return p(f) ? $ : g(f);
    }, arguments);
  };
  b.wbg.__wbg_instanceof_CanvasRenderingContext2d_20bf99ccc051643b = (a) => {
    let b;
    try {
      b = c(a) instanceof CanvasRenderingContext2D;
    } catch (a) {
      b = !1;
    }
    const d = b;
    return d;
  };
  b.wbg.__wbg_setglobalAlpha_d73578e4c446b8b4 = (a, b) => {
    c(a).globalAlpha = b;
  };
  b.wbg.__wbg_setstrokeStyle_c79ba6bc36a7f302 = (a, b) => {
    c(a).strokeStyle = c(b);
  };
  b.wbg.__wbg_setfillStyle_4de94b275f5761f2 = (a, b) => {
    c(a).fillStyle = c(b);
  };
  b.wbg.__wbg_setlineWidth_ea4c8cb72d8cdc31 = (a, b) => {
    c(a).lineWidth = b;
  };
  b.wbg.__wbg_setfont_a4d031cf2c94b4db = (a, b, d) => {
    var e = B(b, d);
    c(a).font = e;
  };
  b.wbg.__wbg_settextAlign_d4f121248c40b910 = (a, b, d) => {
    var e = B(b, d);
    c(a).textAlign = e;
  };
  b.wbg.__wbg_settextBaseline_a36b2a6259ade423 = (a, b, d) => {
    var e = B(b, d);
    c(a).textBaseline = e;
  };
  b.wbg.__wbg_beginPath_c7b9e681f2d031ca = (a) => {
    c(a).beginPath();
  };
  b.wbg.__wbg_stroke_b125233fc8b11e59 = (a) => {
    c(a).stroke();
  };
  b.wbg.__wbg_lineTo_863448482ad2bd29 = (a, b, d) => {
    c(a).lineTo(b, d);
  };
  b.wbg.__wbg_moveTo_5526d0fa563650fa = (a, b, d) => {
    c(a).moveTo(b, d);
  };
  b.wbg.__wbg_setLineDash_aed2919a1550112b = function () {
    return G((a, b) => {
      c(a).setLineDash(c(b));
    }, arguments);
  };
  b.wbg.__wbg_clearRect_05de681275dda635 = (a, b, d, e, f) => {
    c(a).clearRect(b, d, e, f);
  };
  b.wbg.__wbg_fillRect_b5c8166281bac9df = (a, b, d, e, f) => {
    c(a).fillRect(b, d, e, f);
  };
  b.wbg.__wbg_strokeRect_98e37f7c38874af3 = (a, b, d, e, f) => {
    c(a).strokeRect(b, d, e, f);
  };
  b.wbg.__wbg_fillText_6dfde0e3b04c85db = function () {
    return G((a, b, d, e, f) => {
      var g = B(b, d);
      c(a).fillText(g, e, f);
    }, arguments);
  };
  b.wbg.__wbg_type_c7f33162571befe7 = (b, d) => {
    const e = c(d).type;
    const f = o(e, a.__wbindgen_malloc, a.__wbindgen_realloc);
    const g = l;
    r()[b / a6 + X] = g;
    r()[b / a6 + $] = f;
  };
  b.wbg.__wbg_preventDefault_b1a4aafc79409429 = (a) => {
    c(a).preventDefault();
  };
  b.wbg.__wbg_offsetX_1a40c03298c0d8b6 = (a) => {
    const b = c(a).offsetX;
    return b;
  };
  b.wbg.__wbg_offsetY_f75e8c25b9d9b679 = (a) => {
    const b = c(a).offsetY;
    return b;
  };
  b.wbg.__wbg_ctrlKey_008695ce60a588f5 = (a) => {
    const b = c(a).ctrlKey;
    return b;
  };
  b.wbg.__wbg_shiftKey_1e76dbfcdd36a4b4 = (a) => {
    const b = c(a).shiftKey;
    return b;
  };
  b.wbg.__wbg_altKey_07da841b54bd3ed6 = (a) => {
    const b = c(a).altKey;
    return b;
  };
  b.wbg.__wbg_byobRequest_72fca99f9c32c193 = (a) => {
    const b = c(a).byobRequest;
    return p(b) ? $ : g(b);
  };
  b.wbg.__wbg_close_184931724d961ccc = function () {
    return G((a) => {
      c(a).close();
    }, arguments);
  };
  b.wbg.__wbg_close_a994f9425dab445c = function () {
    return G((a) => {
      c(a).close();
    }, arguments);
  };
  b.wbg.__wbg_enqueue_ea194723156c0cc2 = function () {
    return G((a, b) => {
      c(a).enqueue(c(b));
    }, arguments);
  };
  b.wbg.__wbg_removeProperty_fa6d48e2923dcfac = function () {
    return G((b, d, e, f) => {
      var g = B(e, f);
      const h = c(d).removeProperty(g);
      const i = o(h, a.__wbindgen_malloc, a.__wbindgen_realloc);
      const j = l;
      r()[b / a6 + X] = j;
      r()[b / a6 + $] = i;
    }, arguments);
  };
  b.wbg.__wbg_setProperty_ea7d15a2b591aa97 = function () {
    return G((a, b, d, e, f) => {
      var g = B(b, d);
      var h = B(e, f);
      c(a).setProperty(g, h);
    }, arguments);
  };
  b.wbg.__wbg_addEventListener_53b787075bd5e003 = function () {
    return G((a, b, d, e) => {
      var f = B(b, d);
      c(a).addEventListener(f, c(e));
    }, arguments);
  };
  b.wbg.__wbg_addEventListener_4283b15b4f039eb5 = function () {
    return G((a, b, d, e, f) => {
      var g = B(b, d);
      c(a).addEventListener(g, c(e), c(f));
    }, arguments);
  };
  b.wbg.__wbg_removeEventListener_92cb9b3943463338 = function () {
    return G((a, b, d, e) => {
      var f = B(b, d);
      c(a).removeEventListener(f, c(e));
    }, arguments);
  };
  b.wbg.__wbg_instanceof_HtmlElement_3bcc4ff70cfdcba5 = (a) => {
    let b;
    try {
      b = c(a) instanceof HTMLElement;
    } catch (a) {
      b = !1;
    }
    const d = b;
    return d;
  };
  b.wbg.__wbg_style_c3fc3dd146182a2d = (a) => {
    const b = c(a).style;
    return g(b);
  };
  b.wbg.__wbg_offsetWidth_f7da5da36bd7ebc2 = (a) => {
    const b = c(a).offsetWidth;
    return b;
  };
  b.wbg.__wbg_offsetHeight_6a4b02ccf09957d7 = (a) => {
    const b = c(a).offsetHeight;
    return b;
  };
  b.wbg.__wbg_childNodes_118168e8b23bcb9b = (a) => {
    const b = c(a).childNodes;
    return g(b);
  };
  b.wbg.__wbg_nextSibling_709614fdb0fb7a66 = (a) => {
    const b = c(a).nextSibling;
    return p(b) ? $ : g(b);
  };
  b.wbg.__wbg_appendChild_580ccb11a660db68 = function () {
    return G((a, b) => {
      const d = c(a).appendChild(c(b));
      return g(d);
    }, arguments);
  };
  b.wbg.__wbg_cloneNode_e19c313ea20d5d1d = function () {
    return G((a) => {
      const b = c(a).cloneNode();
      return g(b);
    }, arguments);
  };
  b.wbg.__wbg_data_3ce7c145ca4fbcdc = (a) => {
    const b = c(a).data;
    return g(b);
  };
  b.wbg.__wbg_view_7f0ce470793a340f = (a) => {
    const b = c(a).view;
    return p(b) ? $ : g(b);
  };
  b.wbg.__wbg_respond_b1a43b2e3a06d525 = function () {
    return G((a, b) => {
      c(a).respond(b >>> $);
    }, arguments);
  };
  b.wbg.__wbg_deltaX_206576827ededbe5 = (a) => {
    const b = c(a).deltaX;
    return b;
  };
  b.wbg.__wbg_deltaY_032e327e216f2b2b = (a) => {
    const b = c(a).deltaY;
    return b;
  };
  b.wbg.__wbg_length_d0a802565d17eec4 = (a) => {
    const b = c(a).length;
    return b;
  };
  b.wbg.__wbg_error_8e3928cfb8a43e2b = (a) => {
    console.error(c(a));
  };
  b.wbg.__wbg_warn_63bbae1730aead09 = (a) => {
    console.warn(c(a));
  };
  b.wbg.__wbindgen_is_function = (a) => {
    const b = typeof c(a) === a1;
    return b;
  };
  b.wbg.__wbg_newnoargs_e258087cd0daa0ea = (a, b) => {
    var c = B(a, b);
    const d = new Function(c);
    return g(d);
  };
  b.wbg.__wbg_get_e3c254076557e348 = function () {
    return G((a, b) => {
      const d = a7.get(c(a), c(b));
      return g(d);
    }, arguments);
  };
  b.wbg.__wbg_call_27c0f87801dedf93 = function () {
    return G((a, b) => {
      const d = c(a).call(c(b));
      return g(d);
    }, arguments);
  };
  b.wbg.__wbg_new_72fb9a18b5ae2624 = () => {
    const a = new a8();
    return g(a);
  };
  b.wbg.__wbg_self_ce0dbfc45cf2f5be = function () {
    return G(() => {
      const a = self.self;
      return g(a);
    }, arguments);
  };
  b.wbg.__wbg_window_c6fb939a7f436783 = function () {
    return G(() => {
      const a = window.window;
      return g(a);
    }, arguments);
  };
  b.wbg.__wbg_globalThis_d1e6af4856ba331b = function () {
    return G(() => {
      const a = globalThis.globalThis;
      return g(a);
    }, arguments);
  };
  b.wbg.__wbg_global_207b558942527489 = function () {
    return G(() => {
      const a = global.global;
      return g(a);
    }, arguments);
  };
  b.wbg.__wbg_new_28c511d9baebfa89 = (a, b) => {
    var c = B(a, b);
    const d = new _(c);
    return g(d);
  };
  b.wbg.__wbg_call_b3ca7c6051f9bec1 = function () {
    return G((a, b, d) => {
      const e = c(a).call(c(b), c(d));
      return g(e);
    }, arguments);
  };
  b.wbg.__wbg_is_010fdc0f4ab96916 = (a, b) => {
    const d = a8.is(c(a), c(b));
    return d;
  };
  b.wbg.__wbg_new_81740750da40724f = (a, b) => {
    try {
      var c = { a: a, b: b };
      var d = (a, b) => {
        const d = c.a;
        c.a = $;
        try {
          return H(d, c.b, a, b);
        } finally {
          c.a = d;
        }
      };
      const e = new a9(d);
      return g(e);
    } finally {
      c.a = c.b = $;
    }
  };
  b.wbg.__wbg_resolve_b0083a7967828ec8 = (a) => {
    const b = a9.resolve(c(a));
    return g(b);
  };
  b.wbg.__wbg_then_0c86a60e8fcfe9f6 = (a, b) => {
    const d = c(a).then(c(b));
    return g(d);
  };
  b.wbg.__wbg_buffer_12d079cc21e14bdb = (a) => {
    const b = c(a).buffer;
    return g(b);
  };
  b.wbg.__wbg_newwithbyteoffsetandlength_aa4a17c33a06e5cb = (a, b, d) => {
    const e = new a0(c(a), b >>> $, d >>> $);
    return g(e);
  };
  b.wbg.__wbg_set_a47bac70306a19a7 = (a, b, d) => {
    c(a).set(c(b), d >>> $);
  };
  b.wbg.__wbg_length_c20a40f15020d68a = (a) => {
    const b = c(a).length;
    return b;
  };
  b.wbg.__wbg_newwithbyteoffsetandlength_f884af06774ef276 = (a, b, d) => {
    const e = new Float64Array(c(a), b >>> $, d >>> $);
    return g(e);
  };
  b.wbg.__wbg_buffer_dd7f74bc60f1faab = (a) => {
    const b = c(a).buffer;
    return g(b);
  };
  b.wbg.__wbg_byteLength_58f7b4fab1919d44 = (a) => {
    const b = c(a).byteLength;
    return b;
  };
  b.wbg.__wbg_byteOffset_81d60f7392524f62 = (a) => {
    const b = c(a).byteOffset;
    return b;
  };
  b.wbg.__wbg_set_1f9b04f170055d33 = function () {
    return G((a, b, d) => {
      const e = a7.set(c(a), c(b), c(d));
      return e;
    }, arguments);
  };
  b.wbg.__wbindgen_debug_string = (b, d) => {
    const e = s(c(d));
    const f = o(e, a.__wbindgen_malloc, a.__wbindgen_realloc);
    const g = l;
    r()[b / a6 + X] = g;
    r()[b / a6 + $] = f;
  };
  b.wbg.__wbindgen_throw = (a, b) => {
    throw new _(k(a, b));
  };
  b.wbg.__wbindgen_memory = () => {
    const b = a.memory;
    return g(b);
  };
  b.wbg.__wbg_queueMicrotask_481971b0d87f3dd4 = (a) => {
    queueMicrotask(c(a));
  };
  b.wbg.__wbg_queueMicrotask_3cbae2ec6b6cd3d6 = (a) => {
    const b = c(a).queueMicrotask;
    return g(b);
  };
  b.wbg.__wbindgen_closure_wrapper160 = (a, b, c) => {
    const d = u(a, b, 23, v);
    return g(d);
  };
  b.wbg.__wbindgen_closure_wrapper625 = (a, b, c) => {
    const d = w(a, b, aa, x);
    return g(d);
  };
  b.wbg.__wbindgen_closure_wrapper627 = (a, b, c) => {
    const d = w(a, b, aa, x);
    return g(d);
  };
  b.wbg.__wbindgen_closure_wrapper792 = (a, b, c) => {
    const d = u(a, b, 157, y);
    return g(d);
  };
  b.wbg.__wbindgen_closure_wrapper3096 = (a, b, c) => {
    const d = u(a, b, 292, z);
    return g(d);
  };
  return b;
};
let a;
const b = new U(128).fill(V);
b.push(V, W, !0, !1);
let d = b.length;
const h =
  typeof TextDecoder !== Y
    ? new TextDecoder(Z, { ignoreBOM: !0, fatal: !0 })
    : {
        decode: () => {
          throw _(`TextDecoder not available`);
        },
      };
if (typeof TextDecoder !== Y) {
  h.decode();
}
let i = W;
let l = $;
const m =
  typeof TextEncoder !== Y
    ? new TextEncoder(Z)
    : {
        encode: () => {
          throw _(`TextEncoder not available`);
        },
      };
const n =
  typeof m.encodeInto === a1
    ? (a, b) => m.encodeInto(a, b)
    : (a, b) => {
        const c = m.encode(a);
        b.set(c);
        return { read: a.length, written: c.length };
      };
let q = W;
const t =
  typeof a4 === Y
    ? { register: () => {}, unregister: () => {} }
    : new a4((b) => {
        a.__wbindgen_export_2.get(b.dtor)(b.a, b.b);
      });
function A() {
  a.init_panic_hook();
}
function D() {
  const b = a._get_theme_from_local_storage();
  return b !== $;
}
function E(b) {
  const c = o(b, a.__wbindgen_malloc, a.__wbindgen_realloc);
  const d = l;
  a._post_parent(c, d);
}
function F() {
  a.reload_layout();
}
const I =
  typeof a4 === Y
    ? { register: () => {}, unregister: () => {} }
    : new a4((b) => a.__wbg_intounderlyingbytesource_free(b >>> $));
class J {
  __destroy_into_raw() {
    const a = this.__wbg_ptr;
    this.__wbg_ptr = $;
    I.unregister(this);
    return a;
  }
  free() {
    const b = this.__destroy_into_raw();
    a.__wbg_intounderlyingbytesource_free(b);
  }
  type() {
    try {
      const e = a.__wbindgen_add_to_stack_pointer(-a5);
      a.intounderlyingbytesource_type(e, this.__wbg_ptr);
      var b = r()[e / a6 + $];
      var c = r()[e / a6 + X];
      var d = B(b, c);
      if (b !== $) {
        a.__wbindgen_free(b, c, X);
      }
      return d;
    } finally {
      a.__wbindgen_add_to_stack_pointer(a5);
    }
  }
  autoAllocateChunkSize() {
    const b = a.intounderlyingbytesource_autoAllocateChunkSize(this.__wbg_ptr);
    return b >>> $;
  }
  start(b) {
    a.intounderlyingbytesource_start(this.__wbg_ptr, g(b));
  }
  pull(b) {
    const c = a.intounderlyingbytesource_pull(this.__wbg_ptr, g(b));
    return f(c);
  }
  cancel() {
    const b = this.__destroy_into_raw();
    a.intounderlyingbytesource_cancel(b);
  }
}
const K =
  typeof a4 === Y
    ? { register: () => {}, unregister: () => {} }
    : new a4((b) => a.__wbg_intounderlyingsink_free(b >>> $));
class L {
  __destroy_into_raw() {
    const a = this.__wbg_ptr;
    this.__wbg_ptr = $;
    K.unregister(this);
    return a;
  }
  free() {
    const b = this.__destroy_into_raw();
    a.__wbg_intounderlyingsink_free(b);
  }
  write(b) {
    const c = a.intounderlyingsink_write(this.__wbg_ptr, g(b));
    return f(c);
  }
  close() {
    const b = this.__destroy_into_raw();
    const c = a.intounderlyingsink_close(b);
    return f(c);
  }
  abort(b) {
    const c = this.__destroy_into_raw();
    const d = a.intounderlyingsink_abort(c, g(b));
    return f(d);
  }
}
const M =
  typeof a4 === Y
    ? { register: () => {}, unregister: () => {} }
    : new a4((b) => a.__wbg_intounderlyingsource_free(b >>> $));
class N {
  __destroy_into_raw() {
    const a = this.__wbg_ptr;
    this.__wbg_ptr = $;
    M.unregister(this);
    return a;
  }
  free() {
    const b = this.__destroy_into_raw();
    a.__wbg_intounderlyingsource_free(b);
  }
  pull(b) {
    const c = a.intounderlyingsource_pull(this.__wbg_ptr, g(b));
    return f(c);
  }
  cancel() {
    const b = this.__destroy_into_raw();
    a.intounderlyingsource_cancel(b);
  }
}
export default T;
export {
  A as init_panic_hook,
  D as _get_theme_from_local_storage,
  E as _post_parent,
  F as reload_layout,
  J as IntoUnderlyingByteSource,
  L as IntoUnderlyingSink,
  N as IntoUnderlyingSource,
  S as initSync,
};
