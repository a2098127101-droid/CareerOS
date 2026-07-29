(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.CareerNavigation = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function repeatedlyDecode(value) {
    let current = value;
    for (let index = 0; index < 2; index += 1) {
      try {
        const decoded = decodeURIComponent(current);
        if (decoded === current) break;
        current = decoded;
      } catch (_) {
        return "";
      }
    }
    return current;
  }

  function safeSameOriginPath(value, origin) {
    if (typeof value !== "string" || !value.startsWith("/")) return "";
    const decoded = repeatedlyDecode(value);
    if (!decoded || decoded.startsWith("//") || decoded.includes("\\") || /[\u0000-\u001f]/.test(decoded)) {
      return "";
    }
    try {
      const baseOrigin = origin || (typeof location !== "undefined" ? location.origin : "http://localhost");
      const target = new URL(value, baseOrigin);
      if (target.origin !== baseOrigin || !target.pathname.startsWith("/") || target.pathname.startsWith("//")) {
        return "";
      }
      return `${target.pathname}${target.search}${target.hash}`;
    } catch (_) {
      return "";
    }
  }

  return { safeSameOriginPath };
});
