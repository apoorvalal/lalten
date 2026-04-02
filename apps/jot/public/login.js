(() => {
  const mode = document.body.dataset.authMode;
  const ownerTokenKey = window.__OWNER_TOKEN_KEY__ || "md_owner_token";
  const basePath = window.__BASE_PATH__ || "";
  const withBase = (path) => `${basePath}${path}`;
  const form = document.getElementById("auth-form");
  const errorNode = document.getElementById("auth-error");

  restoreOwnerSession().then((restored) => {
    if (restored) {
      window.location.replace(withBase("/"));
      return;
    }

    form.addEventListener("submit", onSubmit);
  });

  async function onSubmit(event) {
    event.preventDefault();
    setError("");

    const formData = new FormData(form);
    const body = Object.fromEntries(formData.entries());
    const endpoint = mode === "setup" ? "/api/auth/setup" : "/api/auth/login";

    try {
      const payload = await api(endpoint, { method: "POST", body });
      window.localStorage.setItem(ownerTokenKey, payload.token);
      await restoreOwnerSession();
      window.location.replace(withBase("/"));
    } catch (error) {
      setError(error.message || "Request failed.");
    }
  }

  async function restoreOwnerSession() {
    const token = window.localStorage.getItem(ownerTokenKey);
    if (!token) {
      return false;
    }

    try {
      await api("/api/auth/token", { method: "POST", body: { token } });
      return true;
    } catch {
      window.localStorage.removeItem(ownerTokenKey);
      return false;
    }
  }

  async function api(url, options = {}) {
    const response = await fetch(withBase(url), {
      method: options.method || "GET",
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
      credentials: "same-origin",
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Request failed.");
    }
    return payload;
  }

  function setError(message) {
    errorNode.textContent = message;
    errorNode.classList.toggle("hidden", !message);
  }
})();
