#!/usr/bin/env bash
set -e

BASE="http://localhost:8000/api/v1"
FHIR="http://localhost:8080/fhir"
PASS=0
FAIL=0

check() {
    local name="$1"
    local expected="$2"
    local actual="$3"
    if [ "$actual" = "$expected" ]; then
        echo "  PASS: $name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $name (expected=$expected actual=$actual)"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Health ==="
check "health-check" "true" "$(curl -sf $BASE/utils/health-check/)"
check "hapi-fhir" "CapabilityStatement" "$(curl -sf $FHIR/metadata | python3 -c 'import sys,json; print(json.load(sys.stdin)["resourceType"])')"

echo ""
echo "=== Auth: create user + token ==="
USER_JSON=$(curl -sf -X POST $BASE/private/users/ -H "Content-Type: application/json" -d '{"role":"PATIENT","display_name":"Smoke Test"}')
USER_ID=$(echo "$USER_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
check "create-user" "PATIENT" "$(echo "$USER_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["role"])')"

TOKEN_JSON=$(curl -sf -X POST "$BASE/auth/dev-token?user_id=$USER_ID")
TOKEN=$(echo "$TOKEN_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
check "dev-token" "bearer" "$(echo "$TOKEN_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token_type"])')"

echo ""
echo "=== Auth: verify identity ==="
ME_JSON=$(curl -sf $BASE/auth/me -H "Authorization: Bearer $TOKEN")
check "auth-me-id" "$USER_ID" "$(echo "$ME_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')"
check "auth-me-role" "PATIENT" "$(echo "$ME_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["role"])')"

echo ""
echo "=== Auth: role enforcement ==="
ADMIN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $BASE/users/ -H "Authorization: Bearer $TOKEN")
check "patient-blocked-from-admin" "403" "$ADMIN_STATUS"

NO_TOKEN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $BASE/auth/me)
check "no-token-401" "401" "$NO_TOKEN_STATUS"

BAD_TOKEN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $BASE/auth/me -H "Authorization: Bearer garbage")
check "bad-token-403" "403" "$BAD_TOKEN_STATUS"

echo ""
echo "=== FHIR: Patient CRUD ==="
PATIENT_JSON=$(curl -sf -X POST $FHIR/Patient -H "Content-Type: application/fhir+json" -d '{"resourceType":"Patient","name":[{"family":"SmokeTest","given":["QA"]}]}')
PATIENT_ID=$(echo "$PATIENT_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
check "fhir-create-patient" "Patient" "$(echo "$PATIENT_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["resourceType"])')"

FETCH_JSON=$(curl -sf $FHIR/Patient/$PATIENT_ID)
check "fhir-read-patient" "SmokeTest" "$(echo "$FETCH_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["name"][0]["family"])')"

FHIR_404=$(curl -s -o /dev/null -w "%{http_code}" $FHIR/Patient/does-not-exist-999)
check "fhir-404" "404" "$FHIR_404"

echo ""
echo "=== Results ==="
echo "  $PASS passed, $FAIL failed"
if [ $FAIL -gt 0 ]; then
    exit 1
fi
