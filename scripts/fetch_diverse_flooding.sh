#!/usr/bin/env bash

set -euo pipefail

endpoint="https://data.cityofnewyork.us/resource/erm2-nwe9.json"
output="nyc311_flooding_diverse_raw.json"
temporary_dir="$(mktemp -d /private/tmp/civicproof-flooding.XXXXXX)"
trap 'rm -rf "$temporary_dir"' EXIT

headers=(--header "Accept: application/json")
if [[ -n "${NYC311_APP_TOKEN:-}" ]]; then
  headers+=(--header "X-App-Token: ${NYC311_APP_TOKEN}")
fi

select_fields="unique_key,created_date,closed_date,agency,complaint_type,descriptor,status,due_date,resolution_description,borough,incident_zip,latitude,longitude"
index=0

while IFS=$'\t' read -r complaint_type descriptor; do
  [[ -z "$complaint_type" ]] && continue
  index=$((index + 1))
  destination="${temporary_dir}/$(printf '%02d' "$index").json"
  where_clause="created_date >= '2025-01-01T00:00:00.000' AND created_date < '2026-07-31T00:00:00.000' AND latitude IS NOT NULL AND longitude IS NOT NULL AND complaint_type = '${complaint_type}' AND descriptor = '${descriptor}'"

  curl --fail-with-body --silent --show-error --get "$endpoint" \
    "${headers[@]}" \
    --data-urlencode "\$select=${select_fields}" \
    --data-urlencode "\$where=${where_clause}" \
    --data-urlencode '$order=created_date DESC,unique_key DESC' \
    --data-urlencode '$limit=30' \
    --output "$destination"

  jq -e 'type == "array"' "$destination" >/dev/null
done <<'PAIRS'
Sewer	Street Flooding (SJ)
Sewer	Manhole Overflow (Use Comments) (SA1)
Sewer	Highway Flooding (SH)
Sewer	RAIN GARDEN FLOODING (SRGFLD)
Sewer Maintenance	Flooding on Street
Sewer Maintenance	Flooding on Highway
DEP Street Condition	Ponding
PAIRS

temporary_output="${temporary_dir}/combined.json"
jq -s 'add | unique_by(.unique_key)' "${temporary_dir}"/[0-9][0-9].json > "$temporary_output"
mv "$temporary_output" "$output"

echo "Saved $(jq 'length' "$output") records to $output"
jq -r '.[] | [.complaint_type, .descriptor] | @tsv' "$output" \
  | sort \
  | uniq -c \
  | sort -nr
