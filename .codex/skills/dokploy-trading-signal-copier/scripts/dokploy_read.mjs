#!/usr/bin/env node
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const SERVICES = {
  "trading-api": {
    type: "application",
    id: "Y3u4LAcWy6f-2Raehj4dN",
    oneEndpoint: "application.one",
    domainEndpoint: "domain.byApplicationId",
    domainArg: "applicationId",
  },
  "trading-dashboard": {
    type: "application",
    id: "lku4v_DVjO_BEJSSQgBZi",
    oneEndpoint: "application.one",
    domainEndpoint: "domain.byApplicationId",
    domainArg: "applicationId",
  },
  mt5docker: {
    type: "compose",
    id: "lyWoSktldNGDOg1ijVsrk",
    oneEndpoint: "compose.one",
    domainEndpoint: "domain.byComposeId",
    domainArg: "composeId",
  },
};

const SECRET_KEY = /(password|secret|token|key|hash|login|api_id|api_hash|server)/i;

function usage() {
  console.error(`Usage:
  dokploy_read.mjs summary
  dokploy_read.mjs app trading-api|trading-dashboard
  dokploy_read.mjs compose mt5docker
  dokploy_read.mjs domains
  dokploy_read.mjs mounts
  dokploy_read.mjs deployments [limit]
`);
  process.exit(2);
}

function readAuth() {
  const envToken = process.env.DOKPLOY_API_KEY || process.env.DOKPLOY_AUTH_TOKEN;
  const envUrl = process.env.DOKPLOY_URL;
  if (envToken && envUrl) {
    return { token: envToken, url: envUrl.replace(/\/$/, "") };
  }

  let dokployPath = "";
  try {
    dokployPath = execFileSync("sh", ["-lc", "command -v dokploy"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    throw new Error("dokploy not found and DOKPLOY_URL/DOKPLOY_API_KEY not set");
  }

  const real = fs.realpathSync(dokployPath);
  const packageRoot = path.dirname(path.dirname(real));
  const configPath = path.join(packageRoot, "config.json");
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  if (!config.url || !config.token) {
    throw new Error("Incomplete Dokploy auth config");
  }
  return { token: config.token, url: config.url.replace(/\/$/, "") };
}

async function trpc(endpoint, json = undefined) {
  const auth = readAuth();
  const input = json === undefined ? "" : `?input=${encodeURIComponent(JSON.stringify({ json }))}`;
  const response = await fetch(`${auth.url}/api/trpc/${endpoint}${input}`, {
    headers: {
      "x-api-key": auth.token,
      "Content-Type": "application/json",
    },
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${endpoint} failed: HTTP ${response.status}: ${text.slice(0, 500)}`);
  }
  const data = JSON.parse(text);
  return data?.result?.data?.json ?? data;
}

function parseEnv(envText) {
  if (typeof envText !== "string") return [];
  return envText
    .split(/\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#") && line.includes("="))
    .map((line) => {
      const [rawKey, ...rest] = line.split("=");
      const key = rawKey.trim();
      const value = SECRET_KEY.test(key) ? "<redacted>" : rest.join("=").trim();
      return { key, value };
    });
}

function compactApp(app) {
  return {
    applicationId: app.applicationId,
    name: app.name,
    appName: app.appName,
    status: app.applicationStatus,
    sourceType: app.sourceType,
    buildType: app.buildType,
    owner: app.owner,
    repository: app.repository,
    branch: app.branch,
    dockerContextPath: app.dockerContextPath,
    dockerBuildStage: app.dockerBuildStage,
    autoDeploy: app.autoDeploy,
    env: parseEnv(app.env),
    createdAt: app.createdAt,
  };
}

function compactCompose(compose) {
  return {
    composeId: compose.composeId,
    name: compose.name,
    appName: compose.appName,
    status: compose.composeStatus,
    sourceType: compose.sourceType,
    owner: compose.owner,
    repository: compose.repository,
    branch: compose.branch,
    env: parseEnv(compose.env),
    composeFile: compose.composeFile,
    createdAt: compose.createdAt,
  };
}

function compactDomain(domain) {
  return {
    domainId: domain.domainId,
    host: domain.host,
    path: domain.path,
    port: domain.port,
    https: domain.https,
    certificateType: domain.certificateType,
    domainType: domain.domainType,
    serviceName: domain.serviceName,
    createdAt: domain.createdAt,
  };
}

function compactMount(mount) {
  return {
    mountId: mount.mountId,
    type: mount.type,
    hostPath: mount.hostPath,
    volumeName: mount.volumeName,
    mountPath: mount.mountPath,
    filePath: mount.filePath,
    serviceType: mount.serviceType,
  };
}

function compactDeployment(dep) {
  return {
    deploymentId: dep.deploymentId,
    title: dep.title,
    commit: (dep.description || "").replace(/^Commit: /, "") || null,
    status: dep.status,
    createdAt: dep.createdAt,
    finishedAt: dep.finishedAt,
    target: dep.application?.name || dep.compose?.name || null,
    appName: dep.application?.appName || dep.compose?.appName || null,
    project: dep.application?.environment?.project?.name || dep.compose?.environment?.project?.name || null,
    errorMessage: dep.errorMessage,
  };
}

async function readOne(serviceName) {
  const svc = SERVICES[serviceName];
  if (!svc) throw new Error(`Unknown service: ${serviceName}`);
  const argName = svc.type === "compose" ? "composeId" : "applicationId";
  const data = await trpc(svc.oneEndpoint, { [argName]: svc.id });
  return svc.type === "compose" ? compactCompose(data) : compactApp(data);
}

async function readDomains() {
  const out = {};
  for (const [name, svc] of Object.entries(SERVICES)) {
    const domains = await trpc(svc.domainEndpoint, { [svc.domainArg]: svc.id });
    out[name] = Array.isArray(domains) ? domains.map(compactDomain) : domains;
  }
  return out;
}

async function readMounts() {
  const out = {};
  for (const [name, svc] of Object.entries(SERVICES)) {
    const mounts = await trpc("mounts.listByServiceId", {
      serviceType: svc.type,
      serviceId: svc.id,
    });
    out[name] = Array.isArray(mounts) ? mounts.map(compactMount) : mounts;
  }
  return out;
}

async function readDeployments(limit = 20) {
  const deployments = await trpc("deployment.allCentralized", {});
  return deployments
    .filter((dep) => {
      const project =
        dep.application?.environment?.project?.name || dep.compose?.environment?.project?.name;
      return project === "Trading Platform";
    })
    .slice(0, limit)
    .map(compactDeployment);
}

async function main() {
  const [command, arg] = process.argv.slice(2);
  let result;
  if (command === "summary") {
    result = {
      apps: [await readOne("trading-api"), await readOne("trading-dashboard")],
      compose: await readOne("mt5docker"),
      domains: await readDomains(),
      mounts: await readMounts(),
      deployments: await readDeployments(10),
    };
  } else if (command === "app") {
    if (!["trading-api", "trading-dashboard"].includes(arg)) usage();
    result = await readOne(arg);
  } else if (command === "compose") {
    if (arg !== "mt5docker") usage();
    result = await readOne(arg);
  } else if (command === "domains") {
    result = await readDomains();
  } else if (command === "mounts") {
    result = await readMounts();
  } else if (command === "deployments") {
    result = await readDeployments(Number(arg || 20));
  } else {
    usage();
  }
  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
