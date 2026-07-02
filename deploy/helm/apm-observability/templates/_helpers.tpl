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
