# Kubernetes deployment (planned)

> ⚠️ **Status: not deployed yet.** This folder contains a Kustomize layout for when we move from Docker Compose → Kubernetes. The current production deployment is still `docker-compose -f infra/docker-compose.yml --profile full up`.

This folder exists to demonstrate that the platform is **designed for Kubernetes from day one** — not as a future rewrite but as a configuration change. The Docker images we already build (`repo-surgeon/surgeon-service:local`, `repo-surgeon/dashboard:local`) are exactly the images these manifests reference.

For the broader k8s migration story (multi-tenancy, sandboxing, HPA, observability), see [`../docs/ARCHITECTURE.md → Future work → Production deployment on Kubernetes`](../docs/ARCHITECTURE.md#future-work).

---

## Layout

```
k8s/
├── README.md                         # this file
├── base/                             # universal manifests, no environment specifics
│   ├── kustomization.yaml
│   ├── namespace.yaml
│   ├── postgres-statefulset.yaml
│   ├── postgres-service.yaml
│   ├── redis-deployment.yaml
│   ├── redis-service.yaml
│   ├── surgeon-deployment.yaml
│   ├── surgeon-service.yaml
│   ├── dashboard-deployment.yaml
│   ├── dashboard-service.yaml
│   ├── configmap.yaml                # non-secret env defaults
│   └── secret.template.yaml          # PLACEHOLDERS ONLY — never commit real values
└── overlays/
    ├── local/                        # kind / minikube / Docker Desktop
    │   ├── kustomization.yaml
    │   └── patches/
    │       └── postgres-emptydir.yaml
    └── production/                   # real cloud cluster
        ├── kustomization.yaml
        └── patches/
            ├── surgeon-hpa.yaml          # CPU-based autoscaling
            ├── surgeon-keda.yaml         # queue-depth scaling for the worker
            ├── ingress.yaml              # cert-manager + nginx ingress
            └── networkpolicy.yaml        # default-deny + allowlist
```

## Why Kustomize and not Helm

For the current shape — small surface area, clearly-defined overlay differences (local vs cloud), no templating logic needed — Kustomize is lighter weight. We may move to Helm later if we need:
- Multi-cluster fan-out
- Conditional includes based on flags
- An upstream chart users can fork

Both are acceptable; Kustomize is the simpler starting point.

## What's intentionally missing (called out as future work)

- **Sandbox CRD** — a custom resource for per-run sandbox pods (gVisor / Kata). Designed in `ARCHITECTURE.md`; implementation pending.
- **External Secrets Operator integration** — `secret.template.yaml` is a placeholder; production should use ESO + AWS Secrets Manager / GCP Secret Manager / Vault.
- **Observability stack** — Prometheus ServiceMonitor + Grafana dashboards + Loki ingestion not yet shipped.
- **Cert-manager Issuer** — referenced in the ingress patch as annotation only; cluster-level Issuer must be installed separately.
- **CloudNativePG or Zalando Postgres Operator** — using a plain StatefulSet for now. Production should use one of these operators for HA + backups.

## How a future deploy would work

```bash
# Local kind cluster
kind create cluster --name repo-surgeon
kubectl apply -k k8s/overlays/local
kubectl -n repo-surgeon port-forward svc/dashboard 3000:3000

# Cloud cluster (after secret population)
kubectl apply -k k8s/overlays/production
```

The Docker images would be pushed to a real registry (ghcr.io/itsdun1/surgeon-service:v1.0.0) instead of `:local`.

## Validating without deploying

```bash
# Render base
kubectl kustomize k8s/base

# Render an overlay
kubectl kustomize k8s/overlays/production

# Validate against the cluster API (dry-run, no apply)
kubectl apply -k k8s/overlays/local --dry-run=client
```
