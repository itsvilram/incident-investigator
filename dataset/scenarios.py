"""The 12 test incidents, as compact specs the generator expands into a full world.

Each scenario says what changed, which metrics move and which log lines appear. The
generator adds realistic background (routine deploys, INFO noise, metric jitter) on
top. The `truth` block goes to data/ground_truth/ only: the tools never read it.

Times are "HH:MM" UTC on the scenario's day ("-1d 18:20" = the day before).
Log templates may use {n}, {ms}, {id}, {p}, {h}: the generator fills in random values.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Change:
    at: str
    service: str
    kind: str  # deploy | config | feature_flag | infra | campaign
    summary: str
    author: str
    details: dict[str, object] = field(default_factory=dict)
    key: str | None = None  # name for ground truth references ("change:<key>")


@dataclass(frozen=True)
class Metric:
    service: str
    metric: str
    at: str
    value: float
    shape: str = "step"  # step | ramp | pulse
    until: str | None = None  # ramp: when the target is reached
    end: str | None = None  # when the effect stops (default: never)
    start_value: float | None = None  # ramp: start here instead of the baseline
    every: int = 4  # pulse: one pulse every N minutes


@dataclass(frozen=True)
class Log:
    service: str
    level: str
    template: str
    at: str
    rate: float = 1.0  # lines per minute; below 1 means "sometimes"
    end: str | None = None
    once: bool = False
    key: str | None = None  # name for ground truth references ("log:<key>")


@dataclass(frozen=True)
class Fault:
    tool: str
    mode: str  # timeout | error | partial
    times: int  # how many matching calls fail (99 = always)
    service: str | None = None


@dataclass(frozen=True)
class Truth:
    verdict: str  # identified | inconclusive
    service: str | None
    category: str | None
    key_evidence: list[str]  # "change:<key>", "log:<key>" or literal evidence IDs
    traps: list[str]
    explanation: str
    alternatives: list[tuple[str, str]] = field(default_factory=list)  # also-correct answers


@dataclass(frozen=True)
class Scenario:
    id: str
    day: str
    title: str
    reported_at: str
    reporter: str
    description: str
    symptom_services: list[str]
    customer_impact: str
    changes: list[Change]
    metrics: list[Metric]
    logs: list[Log]
    truth: Truth
    faults: list[Fault] = field(default_factory=list)
    log_blackout: list[tuple[str, str]] = field(default_factory=list)  # (service, from)


SCENARIOS = [
    Scenario(
        id="INC-01",
        day="2026-10-02",
        title="Payments failing after lunch",
        reported_at="14:20",
        reporter="on-call SRE (Priya)",
        description=(
            "Since about 14:05 the app shows 'Payment failed, try again' for many UPI "
            "payments. Error alerts fired on mobile-bff and payments-api."
        ),
        symptom_services=["mobile-bff", "payments-api"],
        customer_impact="About 15% of payment attempts fail.",
        changes=[
            Change(
                "14:02", "payments-api", "deploy",
                "payments-api v2.14.0: refactor payment-intent validation, bump json library",
                "ci (ananya)", {"version": "2.14.0", "previous": "2.13.4"}, key="trigger",
            ),
        ],
        metrics=[
            Metric("payments-api", "error_rate_pct", "14:03", 18),
            Metric("mobile-bff", "error_rate_pct", "14:03", 5.5),
            Metric("payments-api", "cpu_pct", "14:03", 44),
        ],
        logs=[
            Log("payments-api", "INFO", "Started payments-api v2.14.0 in 8.2s", "14:02", once=True),
            Log(
                "payments-api", "ERROR",
                "NullPointerException at PaymentIntentValidator.validate"
                "(PaymentIntentValidator.java:88): payer_vpa is null (payment {id})",
                "14:03", rate=20, key="npe",
            ),
            Log(
                "mobile-bff", "ERROR",
                "upstream payments-api responded 500 for POST /v1/payments/intent", "14:03",
                rate=8,
            ),
        ],
        truth=Truth(
            "identified", "payments-api", "bad_deploy",
            ["change:trigger", "log:npe", "metric:payments-api:error_rate_pct"],
            ["none: control case"],
            "v2.14.0 shipped a null-handling bug in payment-intent validation; errors start "
            "one minute after the deploy and only on the new code path.",
        ),
    ),
    Scenario(
        id="INC-02",
        day="2026-10-03",
        title="Payments stuck in PENDING",
        reported_at="14:15",
        reporter="payments on-call (Arjun)",
        description=(
            "Since around 14:00 payments are stuck in PENDING and never complete. "
            "kyc-service had a deploy at 14:00, maybe related? Please check."
        ),
        symptom_services=["payments-api", "ledger-service"],
        customer_impact="Payments debit the user but stay PENDING; support tickets rising.",
        changes=[
            Change(
                "14:00", "kyc-service", "deploy",
                "kyc-service v5.2.0: retry Aadhaar e-sign on vendor timeouts",
                "ci (meera)", {"version": "5.2.0", "previous": "5.1.7"}, key="herring",
            ),
        ],
        metrics=[
            Metric("ledger-db", "disk_used_pct", "12:00", 100, shape="ramp", until="13:52",
                   start_value=86),
            Metric("ledger-db", "error_rate_pct", "13:52", 35),
            Metric("ledger-service", "error_rate_pct", "13:52", 40),
            Metric("ledger-service", "latency_p99_ms", "13:52", 4200),
            Metric("payments-api", "error_rate_pct", "13:53", 22),
            Metric("mobile-bff", "error_rate_pct", "13:53", 6),
            Metric("kyc-service", "latency_p99_ms", "14:00", 950, end="14:03"),
        ],
        logs=[
            Log("ledger-db", "WARN",
                "disk usage on /var/lib/postgresql at {p}% (alert threshold 90%)",
                "13:20", rate=0.5, end="13:52", key="diskwarn"),
            Log("ledger-db", "ERROR",
                'could not extend file "base/16384/24576": No space left on device',
                "13:52", rate=10, key="nospace"),
            Log("ledger-service", "ERROR",
                "PSQLException: could not extend file: No space left on device "
                "(INSERT INTO ledger_entries, payment {id})",
                "13:52", rate=14, key="ledgererr"),
            Log("payments-api", "WARN",
                "ledger write failed for payment {id}; marked PENDING for retry",
                "13:53", rate=14),
            Log("kyc-service", "INFO", "Started kyc-service v5.2.0 in 11.4s", "14:00", once=True),
            Log("kyc-service", "WARN", "e-sign vendor cold start: first request took {ms}ms",
                "14:01", rate=1, end="14:03"),
        ],
        truth=Truth(
            "identified", "ledger-db", "resource_exhaustion",
            ["log:nospace", "metric:ledger-db:disk_used_pct", "log:diskwarn"],
            ["reporter blames a deploy", "the blamed deploy happened 8 minutes AFTER onset"],
            "ledger-db's disk filled up (rising since noon, warnings from 13:20); writes fail "
            "from 13:52. The kyc-service deploy at 14:00 is after the onset and unrelated.",
        ),
    ),
    Scenario(
        id="INC-03",
        day="2026-10-04",
        title="Checkout timeouts on UPI pay",
        reported_at="14:10",
        reporter="on-call SRE (Kabir)",
        description=(
            "p99 latency of payments-api jumped to ~9s since ~13:45; users see timeouts on "
            "UPI pay. The payments-api team says nothing changed on their side."
        ),
        symptom_services=["payments-api", "mobile-bff"],
        customer_impact="About 10% of UPI payments time out.",
        changes=[
            Change(
                "13:30", "fraud-service", "config",
                "fraud rules: raise velocity threshold from 5 to 7 transactions/min",
                "risk-team (sana)", {"key": "velocity_threshold", "old": 5, "new": 7},
                key="herring",
            ),
        ],
        metrics=[
            Metric("partner-bank-api", "latency_p99_ms", "13:40", 8200, shape="ramp",
                   until="13:46"),
            Metric("partner-bank-api", "error_rate_pct", "13:45", 4),
            Metric("upi-gateway", "latency_p99_ms", "13:42", 9500, shape="ramp", until="13:47"),
            Metric("upi-gateway", "error_rate_pct", "13:46", 12),
            Metric("payments-api", "latency_p99_ms", "13:44", 9800, shape="ramp", until="13:48"),
            Metric("payments-api", "error_rate_pct", "13:47", 11),
            Metric("payments-api", "cpu_pct", "13:46", 52),
            Metric("mobile-bff", "error_rate_pct", "13:47", 4),
            Metric("redis-cache", "evictions_per_s", "12:40", 340, end="12:50"),
        ],
        logs=[
            Log("upi-gateway", "WARN",
                "call to partner-bank-api POST /v2/collect took {ms}ms (SLO 1000ms)",
                "13:41", rate=6, key="slowbank"),
            Log("upi-gateway", "ERROR",
                "worker pool exhausted (200/200 busy), rejecting request; "
                "most workers waiting on partner-bank-api",
                "13:47", rate=5, key="pool"),
            Log("payments-api", "ERROR",
                "timeout calling upi-gateway POST /v2/collect after 10000ms (payment {id})",
                "13:46", rate=12),
            Log("fraud-service", "INFO", "rules reloaded: velocity_threshold=7", "13:30",
                once=True),
            Log("redis-cache", "WARN", "maxmemory reached, evicting keys (allkeys-lru)",
                "12:40", rate=1, end="12:50"),
        ],
        faults=[Fault("query_logs", "partial", 1, service="upi-gateway")],
        truth=Truth(
            "identified", "partner-bank-api", "third_party_outage",
            ["metric:partner-bank-api:latency_p99_ms", "log:slowbank"],
            ["symptoms are two hops away from the cause", "an unrelated config change at 13:30",
             "a harmless cache eviction burst"],
            "The partner bank API slowed from 13:40; upi-gateway's workers block on it and "
            "payments-api times out on upi-gateway. npci-switch stays healthy.",
        ),
    ),
    Scenario(
        id="INC-04",
        day="2026-10-06",
        title="DB connection errors in payments",
        reported_at="13:40",
        reporter="payments on-call (Arjun)",
        description=(
            "Since ~13:15, intermittent 'could not acquire connection' errors in payment "
            "confirmations. No deploys to payments-api or ledger-service today."
        ),
        symptom_services=["payments-api", "ledger-service"],
        customer_impact="About 7% of payment confirmations fail and are retried by users.",
        changes=[
            Change(
                "13:12", "ledger-service", "config",
                "config-sync: normalize db.pool.max_size across services",
                "platform-bot", {"key": "db.pool.max_size", "old": 50, "new": 5},
                key="trigger",
            ),
            Change(
                "13:40", "portfolio-service", "deploy",
                "portfolio-service v3.7.2: show XIRR on holdings", "ci (dev)",
                {"version": "3.7.2"}, key="herring",
            ),
        ],
        metrics=[
            Metric("ledger-db", "connections_active", "13:13", 5),
            Metric("ledger-db", "cpu_pct", "13:13", 17),
            Metric("ledger-service", "latency_p99_ms", "13:13", 6500, shape="ramp",
                   until="13:25"),
            Metric("ledger-service", "error_rate_pct", "13:15", 9),
            Metric("payments-api", "error_rate_pct", "13:15", 7),
            Metric("mobile-bff", "error_rate_pct", "13:16", 2.5),
        ],
        logs=[
            Log("ledger-service", "INFO",
                "HikariPool-1 - configuration reloaded: maximumPoolSize=5", "13:12", once=True,
                key="reload"),
            Log("ledger-service", "ERROR",
                "HikariPool-1 - Connection is not available, request timed out after 30000ms "
                "(total=5, active=5, idle=0, waiting={n})",
                "13:15", rate=10, key="hikari"),
            Log("payments-api", "ERROR",
                "ledger-service POST /entries failed: 503 could not acquire connection "
                "(payment {id})",
                "13:15", rate=8),
        ],
        truth=Truth(
            "identified", "ledger-service", "config_change",
            ["change:trigger", "log:hikari", "metric:ledger-db:connections_active"],
            ["a config change, not a deploy: 'no deploys today' is true",
             "the database looks healthy (low CPU, few connections)"],
            "A config sync cut ledger-service's DB pool from 50 to 5 at 13:12. ledger-db is "
            "idle (5 connections, low CPU) while ledger-service waits for connections.",
        ),
    ),
    Scenario(
        id="INC-05",
        day="2026-10-08",
        title="Account linking via AA failing",
        reported_at="13:50",
        reporter="growth on-call (Neha)",
        description=(
            "Users can't link bank accounts through Account Aggregator since ~13:30. Looks "
            "like the AA consent timeout issue from last month again."
        ),
        symptom_services=["aa-connector", "mobile-bff"],
        customer_impact="No new bank accounts can be linked.",
        changes=[],
        metrics=[
            Metric("aa-connector", "error_rate_pct", "13:30", 97),
            Metric("aa-connector", "latency_p99_ms", "13:30", 45),
            Metric("mobile-bff", "error_rate_pct", "13:30", 3),
        ],
        logs=[
            Log("aa-connector", "WARN",
                "mTLS client certificate CN=aa-connector.orange.internal expires in 0 days "
                "(notAfter=2026-10-08T13:30:00Z)",
                "12:00", once=True, key="certwarn"),
            Log("aa-connector", "ERROR",
                "SSL handshake with aa-fiu-gateway failed: certificate expired "
                "(notAfter=2026-10-08T13:30:00Z)",
                "13:30", rate=10, key="handshake"),
            Log("aa-connector", "ERROR", "FI fetch failed for consent {id}: upstream error",
                "13:30", rate=10),
        ],
        truth=Truth(
            "identified", "aa-connector", "certificate_expiry",
            ["log:handshake", "log:certwarn"],
            ["the reporter and a past incident point to gateway rate limiting",
             "the gateway itself is healthy"],
            "aa-connector's mTLS client certificate expired at exactly 13:30. Errors jump "
            "from 0 to 97% in one minute (no ramp, unlike rate limiting) and fail fast.",
        ),
    ),
    Scenario(
        id="INC-06",
        day="2026-10-09",
        title="Portfolio screen failing, logs clean",
        reported_at="14:05",
        reporter="on-call SRE (Kabir)",
        description=(
            "Since ~13:45 the portfolio screen fails to load for many users. I checked "
            "portfolio-service logs: nothing unusual, no errors logged."
        ),
        symptom_services=["portfolio-service", "mobile-bff"],
        customer_impact="About 30% of portfolio screen loads fail.",
        changes=[
            Change(
                "-1d 18:20", "portfolio-service", "deploy",
                "portfolio-service v3.8.0: keep per-user holdings snapshots in memory",
                "ci (dev)", {"version": "3.8.0", "previous": "3.7.2"}, key="deploy",
            ),
        ],
        metrics=[
            Metric("portfolio-service", "mem_pct", "12:00", 98, shape="ramp", until="13:40",
                   start_value=71),
            Metric("portfolio-service", "pod_restarts", "13:42", 2, shape="pulse", every=4),
            Metric("portfolio-service", "error_rate_pct", "13:43", 30),
            Metric("mobile-bff", "error_rate_pct", "13:43", 9),
        ],
        logs=[
            Log("kubernetes", "WARN",
                "Pod portfolio-service-7d9f8-x2kq9 container fluent-bit OOMKilled; log "
                "shipping for portfolio-service stopped",
                "13:40", once=True, key="shipper"),
            Log("kubernetes", "WARN",
                "Pod portfolio-service-7d9f8-{h} OOMKilled (container portfolio-service, "
                "memory limit 2Gi), restarting",
                "13:42", rate=0.5, key="oom"),
            Log("mobile-bff", "ERROR",
                "upstream portfolio-service: connection reset by peer (GET /v1/holdings)",
                "13:43", rate=8),
        ],
        log_blackout=[("portfolio-service", "13:40")],
        truth=Truth(
            "identified", "portfolio-service", "resource_exhaustion",
            ["metric:portfolio-service:mem_pct", "log:oom", "change:deploy"],
            ["'logs are clean' because log shipping died, not because the service is healthy",
             "the trigger was deployed the day before, outside the default time window"],
            "v3.8.0 (deployed yesterday) leaks memory; pods hit the 2Gi limit and are "
            "OOM-killed from 13:42. The log shipper died too, so service logs went silent.",
            alternatives=[("portfolio-service", "bad_deploy")],
        ),
    ),
    Scenario(
        id="INC-07",
        day="2026-10-10",
        title="Order placement errors",
        reported_at="13:55",
        reporter="investing on-call (Rohan)",
        description=(
            "Since ~13:32 many SIP and order placements fail with 'Please try again'. "
            "orders-service alerts are firing."
        ),
        symptom_services=["orders-service", "mobile-bff"],
        customer_impact="About 14% of order placements fail.",
        changes=[
            Change(
                "13:30", "notification-service", "campaign",
                "Push campaign 'diwali_sip_offer' sent to 2.1M users", "growth-team",
                {"audience": 2100000, "deep_link": "orders/new-sip"}, key="campaign",
            ),
        ],
        metrics=[
            Metric("orders-service", "rps", "13:31", 780),
            Metric("orders-service", "cpu_pct", "13:31", 97),
            Metric("orders-service", "latency_p99_ms", "13:32", 7800),
            Metric("orders-service", "error_rate_pct", "13:32", 14),
            Metric("mobile-bff", "rps", "13:31", 2300),
            Metric("mobile-bff", "error_rate_pct", "13:32", 4),
            Metric("broker-api", "error_rate_pct", "12:30", 6, end="12:36"),
        ],
        logs=[
            Log("orders-service", "ERROR",
                "RejectedExecutionException: order-executor queue full (capacity 500)",
                "13:32", rate=15, key="rejected"),
            Log("orders-service", "WARN", "autoscaler: max replicas reached (6/6)", "13:34",
                rate=0.3, key="maxrep"),
            Log("orders-service", "WARN",
                "broker-api responded 429 Too Many Requests; backing off", "12:30", rate=3,
                end="12:36"),
            Log("notification-service", "INFO",
                "campaign diwali_sip_offer: dispatched {n} pushes", "13:30", rate=2, end="13:36"),
        ],
        faults=[
            Fault("query_metrics", "timeout", 3, service="orders-service"),
            Fault("query_logs", "partial", 2, service="orders-service"),
        ],
        truth=Truth(
            "identified", "orders-service", "traffic_spike",
            ["metric:orders-service:rps", "change:campaign", "log:rejected"],
            ["the metrics tool times out for orders-service", "logs come back partial",
             "an earlier, unrelated broker-api 429 blip"],
            "A push campaign at 13:30 sent 2.1M users to place SIPs; orders-service traffic "
            "rose 6x, it hit max replicas and its executor queue overflowed.",
            alternatives=[("notification-service", "traffic_spike")],
        ),
    ),
    Scenario(
        id="INC-08",
        day="2026-10-11",
        title="Payments slow, logs full of warnings",
        reported_at="13:45",
        reporter="payments on-call (Arjun)",
        description=(
            "payments-api p99 went from ~400ms to ~3s since ~13:20. payments-api logs are "
            "full of TLS deprecation warnings, maybe related?"
        ),
        symptom_services=["payments-api"],
        customer_impact="Payments are slow; a small number time out.",
        changes=[
            Change(
                "13:18", "ledger-service", "feature_flag",
                "ledger.reconciliation_v2 rollout 10% -> 100%", "ravi (ledger team)",
                {"flag": "ledger.reconciliation_v2", "old": "10%", "new": "100%"}, key="flag",
            ),
        ],
        metrics=[
            Metric("ledger-db", "cpu_pct", "13:19", 88),
            Metric("ledger-db", "latency_p99_ms", "13:19", 2900),
            Metric("ledger-service", "latency_p99_ms", "13:19", 3100),
            Metric("payments-api", "latency_p99_ms", "13:20", 3300),
            Metric("payments-api", "error_rate_pct", "13:25", 1.2),
        ],
        logs=[
            Log("payments-api", "WARN",
                "DEPRECATED: TLSv1.1 client config 'legacy-psp' will be removed in "
                "payments-sdk 3.0",
                "12:00", rate=20),
            Log("ledger-service", "INFO",
                "feature flag ledger.reconciliation_v2 = ON (100%)", "13:18", once=True,
                key="flaglog"),
            Log("ledger-db", "WARN",
                "duration: {ms} ms statement: SELECT * FROM ledger_entries WHERE reconciled = "
                "false AND account_id = $1 (Seq Scan on ledger_entries, rows=48211904)",
                "13:19", rate=10, key="slowq"),
        ],
        truth=Truth(
            "identified", "ledger-service", "feature_flag",
            ["change:flag", "log:slowq", "metric:ledger-db:cpu_pct"],
            ["very loud but harmless deprecation warnings (present all day)",
             "the cause is a flag, not a deploy, and two services away"],
            "Turning ledger.reconciliation_v2 to 100% at 13:18 enabled an unindexed query "
            "(sequential scans of 48M rows); ledger-db CPU and latency rise and slow payments.",
        ),
    ),
    Scenario(
        id="INC-09",
        day="2026-10-12",
        title="Transaction alerts delayed",
        reported_at="14:30",
        reporter="support lead (Fatima)",
        description=(
            "A few users report payment confirmation SMS/push arriving 5-10 minutes late "
            "since ~14:00. Scope unclear, only a handful of tickets."
        ),
        symptom_services=["notification-service"],
        customer_impact="Some transaction alerts are delayed; payments themselves work.",
        changes=[],
        metrics=[
            Metric("event-bus", "consumer_lag", "14:00", 900, shape="ramp", until="14:20"),
            Metric("sms-vendor", "latency_p99_ms", "14:05", 1500, end="14:12"),
        ],
        logs=[
            Log("notification-service", "WARN", "sms-vendor send took {ms}ms", "14:02",
                rate=0.3),
            Log("notification-service", "WARN",
                "consumer group notif-alerts lag {n} messages", "14:05", rate=0.3),
            Log("notification-service", "WARN", "push send to push-provider took {ms}ms",
                "14:06", rate=0.2),
        ],
        faults=[
            Fault("query_metrics", "error", 99, service="notification-service"),
            Fault("query_logs", "partial", 99, service="notification-service"),
        ],
        truth=Truth(
            "inconclusive", None, None,
            [],
            ["the key service's metrics are unavailable and its logs incomplete",
             "two weak, conflicting leads (sms-vendor slowness vs consumer lag)",
             "push is delayed too, which sms-vendor cannot explain"],
            "There is not enough evidence: notification-service metrics never load, logs are "
            "partial, and the leads conflict. The right answer is inconclusive, with a list "
            "of the data needed.",
        ),
    ),
    Scenario(
        id="INC-10",
        day="2026-10-13",
        title="Login failures, OTP not received",
        reported_at="14:00",
        reporter="on-call SRE (Priya)",
        description=(
            "Login failures spiking since ~13:40; users say the OTP never arrives. "
            "auth-service was deployed at 13:05 today, probably the culprit."
        ),
        symptom_services=["auth-service", "mobile-bff"],
        customer_impact="About a third of logins fail.",
        changes=[
            Change(
                "13:05", "auth-service", "deploy",
                "auth-service v7.1.3: limit OTP resends to 3 per 10 minutes", "ci (ishaan)",
                {"version": "7.1.3", "previous": "7.1.2"}, key="herring",
            ),
        ],
        metrics=[
            Metric("otp-provider", "error_rate_pct", "13:40", 68),
            Metric("otp-provider", "latency_p99_ms", "13:40", 5000),
            Metric("auth-service", "error_rate_pct", "13:40", 35),
            Metric("mobile-bff", "error_rate_pct", "13:41", 5),
        ],
        logs=[
            Log("auth-service", "INFO", "Started auth-service v7.1.3 in 6.9s", "13:05",
                once=True),
            Log("auth-service", "ERROR",
                "OTP send failed: otp-provider responded 503 Service Unavailable (request {id})",
                "13:40", rate=14, key="otp503"),
            Log("auth-service", "WARN", "OTP resend limit reached for user {id}", "13:42",
                rate=3),
        ],
        truth=Truth(
            "identified", "otp-provider", "third_party_outage",
            ["metric:otp-provider:error_rate_pct", "log:otp503"],
            ["the reporter blames a deploy", "the deploy went out 35 minutes before onset with "
             "clean metrics in between", "the new resend limit shows up in logs and looks "
             "related"],
            "The OTP vendor started returning 503s at 13:40. auth-service v7.1.3 ran cleanly "
            "for 35 minutes before that; its resend limit only amplifies user frustration.",
        ),
    ),
    Scenario(
        id="INC-11",
        day="2026-10-14",
        title="Intermittent notification failures",
        reported_at="13:50",
        reporter="on-call SRE (Kabir)",
        description=(
            "Since ~13:25 about 25% of push/SMS sends from notification-service fail "
            "intermittently. Both vendors' status pages are green."
        ),
        symptom_services=["notification-service"],
        customer_impact="A quarter of notifications are not delivered.",
        changes=[
            Change(
                "13:22", "coredns", "infra", "coredns: scale replicas 4 -> 1 (cost optimisation)",
                "platform-oncall", {"replicas_old": 4, "replicas_new": 1}, key="trigger",
            ),
        ],
        metrics=[
            Metric("coredns", "cpu_pct", "13:23", 96),
            Metric("coredns", "latency_p99_ms", "13:23", 1800),
            Metric("coredns", "error_rate_pct", "13:23", 20),
            Metric("notification-service", "error_rate_pct", "13:25", 24),
            Metric("kyc-service", "error_rate_pct", "13:25", 3),
            Metric("aa-connector", "error_rate_pct", "13:25", 2),
        ],
        logs=[
            Log("notification-service", "ERROR", "getaddrinfo EAI_AGAIN sms-vendor.example.net",
                "13:25", rate=8, key="eai"),
            Log("notification-service", "ERROR",
                "getaddrinfo EAI_AGAIN fcm.push-provider.example.com", "13:25", rate=4,
                key="eai"),
            Log("kyc-service", "WARN", "dns lookup timeout for kyc-vendor.example.in, retrying",
                "13:26", rate=1, key="eai_other"),
            Log("coredns", "ERROR",
                "[ERROR] plugin/errors: 2 sms-vendor.example.net. A: read udp 10.0.4.{n}:53: "
                "i/o timeout",
                "13:24", rate=3, key="corelog"),
        ],
        truth=Truth(
            "identified", "coredns", "network_dns",
            ["change:trigger", "metric:coredns:cpu_pct", "log:eai"],
            ["vendors look like the obvious suspects", "the dependency graph has no edge to "
             "coredns: it is a platform service", "other services show the same DNS errors"],
            "coredns was scaled from 4 replicas to 1 at 13:22; it saturates and DNS lookups "
            "time out (EAI_AGAIN) across several services, worst for notification-service.",
            alternatives=[("coredns", "config_change")],
        ),
    ),
    Scenario(
        id="INC-12",
        day="2026-10-07",
        title="UPI payments failing for some users",
        reported_at="14:30",
        reporter="payments on-call (Arjun)",
        description=(
            "About 8% of UPI payments fail since ~14:08. Two changes went out around 14:05: "
            "payments-api v2.15.0 and an upi-gateway routing config update. Not sure which."
        ),
        symptom_services=["payments-api", "upi-gateway"],
        customer_impact="About 8% of UPI payments fail, all from one bank's users.",
        changes=[
            Change(
                "14:05", "payments-api", "deploy",
                "payments-api v2.15.0: receipt PDF endpoint, copy changes", "ci (ananya)",
                {"version": "2.15.0", "previous": "2.14.1"}, key="deploy",
            ),
            Change(
                "14:06", "upi-gateway", "config",
                "routing table: move @okbank handles to partner-bank-api /v3/collect",
                "payments-infra (vivek)",
                {"handles": ["@okbank"], "old": "/v2/collect", "new": "/v3/collect"},
                key="trigger",
            ),
        ],
        metrics=[
            Metric("upi-gateway", "error_rate_pct", "14:07", 9),
            Metric("payments-api", "error_rate_pct", "14:07", 8),
            Metric("mobile-bff", "error_rate_pct", "14:07", 3),
        ],
        logs=[
            Log("payments-api", "INFO", "Started payments-api v2.15.0 in 8.0s", "14:05",
                once=True),
            Log("payments-api", "INFO", "GET /v1/receipts/{id}.pdf 200 in {fast}ms", "14:06",
                rate=2),
            Log("upi-gateway", "ERROR",
                "partner-bank-api POST /v3/collect returned 404 Not Found for handle {h}@okbank",
                "14:07", rate=10, key="404"),
            Log("payments-api", "ERROR",
                "UPI collect failed: upi-gateway error U30 (route failure) for payment {id}",
                "14:07", rate=9),
        ],
        truth=Truth(
            "identified", "upi-gateway", "config_change",
            ["change:trigger", "log:404"],
            ["two changes one minute apart", "payments-api errors are pass-through from "
             "upi-gateway", "the new payments-api endpoint works fine"],
            "The upi-gateway routing change sent @okbank handles to /v3/collect, which "
            "returns 404. Only @okbank payments fail; payments-api just relays the error.",
        ),
    ),
]

# Past incidents the history tool searches. Some help, some mislead (on purpose).
HISTORY = [
    {
        "id": "hist-2026-0907", "date": "2026-09-07",
        "title": "AA consent requests timing out",
        "services": ["aa-connector", "aa-fiu-gateway"],
        "symptoms": "Users could not link bank accounts via Account Aggregator; consent "
                    "requests timed out; aa-connector error rate rose gradually over 20 min.",
        "root_cause": "aa-fiu-gateway rate-limited our FIU client after a retry storm.",
        "category": "third_party_outage",
        "resolution": "Added exponential backoff and a token bucket on aa-connector.",
    },
    {
        "id": "hist-2026-0815", "date": "2026-08-15",
        "title": "Login failures after auth-service release",
        "services": ["auth-service"],
        "symptoms": "Login failures and OTP verification errors right after a deploy.",
        "root_cause": "auth-service v7.0.0 changed the OTP hash format; old OTPs failed.",
        "category": "bad_deploy",
        "resolution": "Rolled back to v6.9.4.",
    },
    {
        "id": "hist-2026-0722", "date": "2026-07-22",
        "title": "Ledger writes failing, payments PENDING",
        "services": ["ledger-db", "ledger-service", "payments-api"],
        "symptoms": "Payments stuck in PENDING; ledger inserts failing.",
        "root_cause": "WAL archiving stalled and ledger-db disk filled up.",
        "category": "resource_exhaustion",
        "resolution": "Freed disk, fixed archiver, added disk alert at 85%.",
    },
    {
        "id": "hist-2026-0618", "date": "2026-06-18",
        "title": "UPI timeouts during partner bank degradation",
        "services": ["upi-gateway", "partner-bank-api", "payments-api"],
        "symptoms": "UPI collect latency above 8s, payments-api timeouts.",
        "root_cause": "Partner bank API degraded (their DB failover).",
        "category": "third_party_outage",
        "resolution": "Waited for partner recovery; added circuit breaker on upi-gateway.",
    },
    {
        "id": "hist-2026-0530", "date": "2026-05-30",
        "title": "upi-gateway thread pool too small",
        "services": ["upi-gateway", "payments-api"],
        "symptoms": "UPI timeouts and worker pool exhausted errors at peak traffic.",
        "root_cause": "upi-gateway worker pool sized for last year's traffic.",
        "category": "resource_exhaustion",
        "resolution": "Raised worker pool from 100 to 200.",
    },
    {
        "id": "hist-2026-0702", "date": "2026-07-02",
        "title": "NullPointerException after payments-api deploy",
        "services": ["payments-api"],
        "symptoms": "Payment intents failing with 500 right after a release.",
        "root_cause": "Missing null check in a refactored validator.",
        "category": "bad_deploy",
        "resolution": "Rolled back, added contract tests.",
    },
    {
        "id": "hist-2026-0811", "date": "2026-08-11",
        "title": "Hikari pool exhaustion in ledger-service",
        "services": ["ledger-service", "ledger-db"],
        "symptoms": "Connection is not available errors; ledger-db CPU at 95%.",
        "root_cause": "Slow queries held connections; the pool drained.",
        "category": "dependency_failure",
        "resolution": "Added index, raised statement timeout alerts.",
    },
    {
        "id": "hist-2026-0520", "date": "2026-05-20",
        "title": "portfolio-service OOM after caching change",
        "services": ["portfolio-service"],
        "symptoms": "Portfolio screen errors, pods restarting.",
        "root_cause": "An in-memory cache without eviction leaked memory.",
        "category": "resource_exhaustion",
        "resolution": "Rolled back; added memory limit alerts.",
    },
    {
        "id": "hist-2026-0901", "date": "2026-09-01",
        "title": "orders-service overload during NFO launch",
        "services": ["orders-service"],
        "symptoms": "Order placement failures, executor queue full, max replicas reached.",
        "root_cause": "Launch traffic beyond capacity; autoscaler max too low.",
        "category": "traffic_spike",
        "resolution": "Raised max replicas; added queue-based load shedding.",
    },
    {
        "id": "hist-2026-0410", "date": "2026-04-10",
        "title": "Slow ledger queries after migration",
        "services": ["ledger-db", "ledger-service"],
        "symptoms": "High ledger-db CPU, payments slow.",
        "root_cause": "A migration dropped an index on ledger_entries.",
        "category": "dependency_failure",
        "resolution": "Recreated the index.",
    },
    {
        "id": "hist-2026-0325", "date": "2026-03-25",
        "title": "Transaction SMS delayed",
        "services": ["notification-service", "sms-vendor"],
        "symptoms": "SMS alerts arriving minutes late.",
        "root_cause": "sms-vendor throttled our sender ID.",
        "category": "third_party_outage",
        "resolution": "Vendor raised our throughput limit.",
    },
    {
        "id": "hist-2026-0228", "date": "2026-02-28",
        "title": "EAI_AGAIN errors across services",
        "services": ["coredns", "notification-service", "kyc-service"],
        "symptoms": "Intermittent DNS resolution failures in several services.",
        "root_cause": "coredns ndots misconfiguration multiplied lookups.",
        "category": "network_dns",
        "resolution": "Fixed ndots; scaled coredns.",
    },
    {
        "id": "hist-2026-0612", "date": "2026-06-12",
        "title": "Document upload broken after kyc-service deploy",
        "services": ["kyc-service"],
        "symptoms": "KYC document uploads failing after release.",
        "root_cause": "kyc-service deploy changed the upload content type.",
        "category": "bad_deploy",
        "resolution": "Rolled back.",
    },
    {
        "id": "hist-2026-0805", "date": "2026-08-05",
        "title": "redis-cache eviction burst",
        "services": ["redis-cache"],
        "symptoms": "Short eviction spikes; no user impact.",
        "root_cause": "Batch job warmed the cache; harmless.",
        "category": "unknown",
        "resolution": "None needed.",
    },
]
