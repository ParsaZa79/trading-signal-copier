#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Read-only DNS, SMTP STARTTLS, and negative relay checks for the mail service.

Usage:
  check-mail.sh [options]

Options:
  --domain DOMAIN            Mail domain to inspect.
  --mail-host HOST           Public SMTP host and certificate name.
  --connect-host HOST        Address to connect to (default: --mail-host value).
  --expected-ip ADDRESS      Require A and PTR to agree with this address.
  --dkim-selector SELECTOR   Also query SELECTOR._domainkey.DOMAIN.
  --port 25|587              Check SMTP STARTTLS on this port (default: 25).
  --expected-sha256-fingerprint HEX
                              Require the presented leaf certificate fingerprint.
  --no-sni                    Omit TLS SNI to prove the server's default certificate.
  --relay-recipient ADDRESS  Perform an unauthenticated RCPT-only relay rejection test.
  --dns-only                 Run DNS checks only.
  --smtp-only                Run SMTP checks only.
  -h, --help                 Show this help.

The relay probe stops after RCPT and never submits message data. Use a non-local
recipient address you control. No configuration is changed by this script.
EOF
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

DOMAIN='kiaparsaprintingmoneymachine.cloud'
MAIL_HOST='mail.kiaparsaprintingmoneymachine.cloud'
CONNECT_HOST=''
EXPECTED_IP=''
DKIM_SELECTOR=''
PORT='25'
RELAY_RECIPIENT=''
EXPECTED_SHA256_FINGERPRINT=''
NO_SNI=0
RUN_DNS=1
RUN_SMTP=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      [[ $# -ge 2 ]] || die "--domain requires a value"
      DOMAIN="$2"
      shift 2
      ;;
    --mail-host)
      [[ $# -ge 2 ]] || die "--mail-host requires a value"
      MAIL_HOST="$2"
      shift 2
      ;;
    --connect-host)
      [[ $# -ge 2 ]] || die "--connect-host requires a value"
      CONNECT_HOST="$2"
      shift 2
      ;;
    --expected-ip)
      [[ $# -ge 2 ]] || die "--expected-ip requires a value"
      EXPECTED_IP="$2"
      shift 2
      ;;
    --dkim-selector)
      [[ $# -ge 2 ]] || die "--dkim-selector requires a value"
      DKIM_SELECTOR="$2"
      shift 2
      ;;
    --port)
      [[ $# -ge 2 ]] || die "--port requires a value"
      PORT="$2"
      shift 2
      ;;
    --relay-recipient)
      [[ $# -ge 2 ]] || die "--relay-recipient requires a value"
      RELAY_RECIPIENT="$2"
      shift 2
      ;;
    --expected-sha256-fingerprint)
      [[ $# -ge 2 ]] || die "--expected-sha256-fingerprint requires a value"
      EXPECTED_SHA256_FINGERPRINT="$2"
      shift 2
      ;;
    --no-sni)
      NO_SNI=1
      shift
      ;;
    --dns-only)
      RUN_DNS=1
      RUN_SMTP=0
      shift
      ;;
    --smtp-only)
      RUN_DNS=0
      RUN_SMTP=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ "$PORT" == '25' || "$PORT" == '587' ]] || die "--port must be 25 or 587"
CONNECT_HOST="${CONNECT_HOST:-$MAIL_HOST}"

if [[ -n "$EXPECTED_SHA256_FINGERPRINT" ]]; then
  EXPECTED_SHA256_FINGERPRINT="$(
    printf '%s' "$EXPECTED_SHA256_FINGERPRINT" |
      tr -d ':' |
      tr '[:lower:]' '[:upper:]'
  )"
  [[ "$EXPECTED_SHA256_FINGERPRINT" =~ ^[0-9A-F]{64}$ ]] || \
    die "--expected-sha256-fingerprint must contain exactly 64 hexadecimal digits"
fi

check_dns() {
  command -v dig >/dev/null 2>&1 || die "dig is required for DNS checks"

  local a_records mx_records spf_records dmarc_records ptr_records=''
  a_records="$(dig +short A "$MAIL_HOST")"
  mx_records="$(dig +short MX "$DOMAIN")"
  spf_records="$(dig +short TXT "$DOMAIN")"
  dmarc_records="$(dig +short TXT "_dmarc.${DOMAIN}")"

  [[ -n "$a_records" ]] || die "DNS A record for $MAIL_HOST is missing"
  grep -Fq "${MAIL_HOST}." <<<"$mx_records" || \
    die "DNS MX for $DOMAIN does not reference $MAIL_HOST"
  grep -Fqi 'v=spf1' <<<"$spf_records" || die "DNS SPF record is missing"
  grep -Fqi 'v=DMARC1' <<<"$dmarc_records" || die "DNS DMARC record is missing"

  if [[ -n "$EXPECTED_IP" ]]; then
    grep -Fxq "$EXPECTED_IP" <<<"$a_records" || \
      die "DNS A record does not contain the expected address"
    ptr_records="$(dig +short -x "$EXPECTED_IP")"
    grep -Fxq "${MAIL_HOST}." <<<"$ptr_records" || \
      die "DNS PTR does not resolve to $MAIL_HOST"
  fi

  if [[ -n "$DKIM_SELECTOR" ]]; then
    local dkim_records
    dkim_records="$(dig +short TXT "${DKIM_SELECTOR}._domainkey.${DOMAIN}")"
    grep -Fqi 'v=DKIM1' <<<"$dkim_records" || die "DNS DKIM record is missing"
  fi

  printf '%s\n' 'DNS checks passed.'
}

check_starttls() {
  command -v openssl >/dev/null 2>&1 || die "openssl is required for STARTTLS checks"

  local work_dir transcript leaf_certificate metadata line fingerprint=''
  local -a s_client_arguments
  work_dir="$(mktemp -d)"
  transcript="$work_dir/s_client.txt"
  leaf_certificate="$work_dir/leaf.pem"

  s_client_arguments=(
    s_client
    -connect "${CONNECT_HOST}:${PORT}"
    -starttls smtp
    -verify_hostname "$MAIL_HOST"
    -verify_return_error
    -showcerts
  )
  if [[ "$NO_SNI" -eq 1 ]]; then
    s_client_arguments+=( -noservername )
  else
    s_client_arguments+=( -servername "$MAIL_HOST" )
  fi

  if ! printf 'QUIT\r\n' | openssl "${s_client_arguments[@]}" \
    >"$transcript" 2>/dev/null; then
    rm -rf "$work_dir"
    die "SMTP STARTTLS certificate or handshake verification failed"
  fi

  awk '
    /-----BEGIN CERTIFICATE-----/ { capture = 1 }
    capture { print }
    /-----END CERTIFICATE-----/ { exit }
  ' "$transcript" > "$leaf_certificate"
  [[ -s "$leaf_certificate" ]] || {
    rm -rf "$work_dir"
    die "SMTP STARTTLS did not present a leaf certificate"
  }
  if ! metadata="$(openssl x509 -in "$leaf_certificate" -noout \
    -fingerprint -sha256 -serial -enddate)"; then
    rm -rf "$work_dir"
    die "could not inspect the SMTP leaf certificate"
  fi
  while IFS= read -r line; do
    if [[ "$line" == *Fingerprint=* || "$line" == *fingerprint=* ]]; then
      fingerprint="${line#*=}"
      fingerprint="$(
        printf '%s' "$fingerprint" |
          tr -d ':' |
          tr '[:lower:]' '[:upper:]'
      )"
      break
    fi
  done <<< "$metadata"
  [[ "$fingerprint" =~ ^[0-9A-F]{64}$ ]] || {
    rm -rf "$work_dir"
    die "could not parse the SMTP leaf certificate SHA-256 fingerprint"
  }
  if [[ -n "$EXPECTED_SHA256_FINGERPRINT" && \
        "$fingerprint" != "$EXPECTED_SHA256_FINGERPRINT" ]]; then
    rm -rf "$work_dir"
    die "SMTP leaf certificate SHA-256 fingerprint does not match the expected certificate"
  fi
  printf '%s\n' "$metadata"
  rm -rf "$work_dir"
  printf 'SMTP STARTTLS check passed on port %s.\n' "$PORT"
}

check_relay() {
  [[ -n "$RELAY_RECIPIENT" ]] || return 0
  command -v swaks >/dev/null 2>&1 || die "swaks is required for the relay check"

  local transcript swaks_status rcpt_line rcpt_code
  transcript="$(mktemp)"
  trap 'rm -f -- "${transcript:-}"' EXIT

  if swaks \
    --server "$CONNECT_HOST" \
    --port "$PORT" \
    --tls \
    --tls-sni "$MAIL_HOST" \
    --from 'relay-probe@invalid.example' \
    --to "$RELAY_RECIPIENT" \
    --quit-after RCPT \
    >"$transcript" 2>&1; then
    swaks_status=0
  else
    swaks_status=$?
  fi

  # Examine only the first SMTP response after the RCPT command. Greeting and
  # EHLO 2xx lines occur earlier and cannot establish whether relay was accepted.
  rcpt_line="$(awk '
    /RCPT TO:/ { after_rcpt = 1; next }
    after_rcpt && /[245][0-9][0-9][ -]/ { print; exit }
  ' "$transcript")"
  rcpt_code="$(sed -E 's/^.*[^0-9]([245][0-9]{2})[ -].*$/\1/' <<<"$rcpt_line")"

  if [[ "$rcpt_code" =~ ^2[0-9][0-9]$ ]] || \
     [[ "$swaks_status" -eq 0 && ! "$rcpt_code" =~ ^5[0-9][0-9]$ ]]; then
    die "relay probe was accepted; investigate possible open relay"
  fi
  [[ "$rcpt_code" =~ ^5[0-9][0-9]$ ]] || \
    die "relay probe did not produce a definitive 5xx rejection"
  rm -f -- "$transcript"
  trap - EXIT
  printf '%s\n' 'Unauthenticated relay was rejected before DATA.'
}

if [[ "$RUN_DNS" -eq 1 ]]; then
  check_dns
fi
if [[ "$RUN_SMTP" -eq 1 ]]; then
  check_starttls
  check_relay
elif [[ -n "$RELAY_RECIPIENT" ]]; then
  die "--relay-recipient cannot be combined with --dns-only"
fi
