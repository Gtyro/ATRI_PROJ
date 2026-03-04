const truncate = (value, maxLength = 800) => {
  if (!value) {
    return "";
  }
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength)}...(truncated)`;
};

export const createRequestDiagnostics = (page, { maxEntries = 200 } = {}) => {
  const events = [];

  const pushEvent = (entry) => {
    events.push({
      timestamp: new Date().toISOString(),
      ...entry,
    });
    if (events.length > maxEntries) {
      events.shift();
    }
  };

  const onRequest = (request) => {
    pushEvent({
      type: "request",
      method: request.method(),
      url: request.url(),
      resourceType: request.resourceType(),
      postData: truncate(request.postData() || ""),
    });
  };

  const onResponse = (response) => {
    const request = response.request();
    pushEvent({
      type: "response",
      method: request.method(),
      url: response.url(),
      status: response.status(),
      ok: response.ok(),
    });
  };

  const onRequestFailed = (request) => {
    pushEvent({
      type: "requestfailed",
      method: request.method(),
      url: request.url(),
      failureText: request.failure()?.errorText || "unknown",
    });
  };

  page.on("request", onRequest);
  page.on("response", onResponse);
  page.on("requestfailed", onRequestFailed);

  const dispose = () => {
    page.off("request", onRequest);
    page.off("response", onResponse);
    page.off("requestfailed", onRequestFailed);
  };

  const attach = async (testInfo, error) => {
    const payload = {
      title: testInfo.title,
      project: testInfo.project.name,
      retry: testInfo.retry,
      errorMessage: error?.message || null,
      eventCount: events.length,
      events,
    };

    await testInfo.attach("request-log.json", {
      body: Buffer.from(`${JSON.stringify(payload, null, 2)}\n`, "utf-8"),
      contentType: "application/json",
    });
  };

  return {
    attach,
    dispose,
  };
};
