const encodeBase64Url = (value) => {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
};

export const buildTestJwt = (expiresInSeconds = 3600) => {
  const header = encodeBase64Url({ alg: "HS256", typ: "JWT" });
  const payload = encodeBase64Url({
    sub: "admin",
    exp: Math.floor(Date.now() / 1000) + expiresInSeconds,
  });
  return `${header}.${payload}.signature`;
};

export const seedAuthenticatedStorage = async (
  page,
  { username = "admin", token = buildTestJwt() } = {},
) => {
  await page.addInitScript(
    ({ localToken, userName }) => {
      localStorage.setItem("token", localToken);
      localStorage.setItem("refresh_token", "refresh-token");
      localStorage.setItem("user", JSON.stringify({ username: userName }));
    },
    {
      localToken: token,
      userName: username,
    },
  );
  return token;
};
