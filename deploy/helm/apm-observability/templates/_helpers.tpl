{{/* Chart name (overridable). */}}
{{- define "apm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Fully qualified app name. */}}
{{- define "apm.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{/* Common labels. */}}
{{- define "apm.labels" -}}
app.kubernetes.io/name: {{ include "apm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: apm-observability
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* Selector labels. */}}
{{- define "apm.selectorLabels" -}}
app.kubernetes.io/name: {{ include "apm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Selector for the web workload specifically.

apm.selectorLabels alone (name+instance) is shared by every pod this chart ships —
the bundled Postgres and the migrate hook Job included — so using it as the app
Service's selector puts the Postgres pod in the Service's endpoint pool. Postgres
has no listener on the HTTP port, so a large share of Service traffic is refused,
and during an upgrade the migrate pod joins too. The component discriminator keeps
the Service, PodMonitor and app workload pointing at web pods only.
*/}}
{{- define "apm.webSelectorLabels" -}}
{{ include "apm.selectorLabels" . }}
app.kubernetes.io/component: web
{{- end -}}

{{/* Effective Secret name: an externally-managed one if provided, else ours. */}}
{{- define "apm.secretName" -}}
{{- if .Values.existingSecret -}}
{{- .Values.existingSecret -}}
{{- else -}}
{{- printf "%s-secret" (include "apm.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/* Effective Postgres host. */}}
{{- define "apm.postgresHost" -}}
{{- if .Values.postgres.host -}}
{{- .Values.postgres.host -}}
{{- else if .Values.postgres.enabled -}}
{{- printf "%s-postgres" (include "apm.fullname" .) -}}
{{- else -}}
{{- .Values.config.POSTGRES_HOST | default "db" -}}
{{- end -}}
{{- end -}}

{{/*
Runtime env that must be computed per-pod rather than baked into the ConfigMap.

Django rejects any request whose Host header is not in ALLOWED_HOSTS with a 400,
and Prometheus scrapes pods by IP (podAnnotations point it at :8000/metrics), so
without the pod IP here every scrape 400s, the canary AnalysisTemplate sees no
data, and the rollout aborts. Service DNS is included for the same reason on
Service/Ingress traffic. POD_IP is declared first so kubelet expands $(POD_IP).
These entries override the ConfigMap's DJANGO_ALLOWED_HOSTS (env beats envFrom).
*/}}
{{- define "apm.runtimeEnv" -}}
- name: POD_IP
  valueFrom:
    fieldRef:
      fieldPath: status.podIP
- name: DJANGO_ALLOWED_HOSTS
  value: "{{ .Values.config.DJANGO_ALLOWED_HOSTS }},$(POD_IP),{{ include "apm.fullname" . }},{{ include "apm.fullname" . }}.{{ .Release.Namespace }}.svc.cluster.local"
{{- end -}}
