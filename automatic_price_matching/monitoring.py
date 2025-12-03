import sentry_sdk


# 1. Track fallback usage
def record_fallback(code: str, name: str):
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("component", "PriceMatching")
        scope.set_tag("fallback", "true")
        scope.set_extra("code", code or "")
        scope.set_extra("name", name or "")
        sentry_sdk.capture_message("Fallback pricing applied", level="info")


# 2. Track price overrides
def record_price_override(code, known_price, user_price):
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("component", "PriceMatching")
        scope.set_tag("override", "true")
        scope.set_extra("code", code)
        scope.set_extra("known_price", str(known_price))
        scope.set_extra("user_price", str(user_price))
        sentry_sdk.capture_message("User price override detected", level="info")


# 3. Track missing AHSP price
def record_missing_price(code):
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("component", "PriceMatching")
        scope.set_tag("price_missing", "true")
        scope.set_extra("code", code)
        sentry_sdk.capture_message("AHSP price missing", level="info")


# 4. Cost anomaly detection
def record_cost_anomaly(cost, volume, price, code):
    if cost > 1_000_000_000:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("component", "PriceMatching")
            scope.set_tag("anomaly", "large_cost")
            scope.set_extra("cost", str(cost))
            scope.set_extra("volume", str(volume))
            scope.set_extra("price", str(price))
            scope.set_extra("code", code)
            sentry_sdk.capture_message("Suspiciously large total cost", level="warning")


# 5. Track batch processing errors
def record_batch_errors(batch_size, errors_count):
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("component", "PriceMatchingBatch")
        scope.set_tag("batch_size", batch_size)
        scope.set_tag("validation_errors", errors_count)
        sentry_sdk.capture_message(
            f"Batch had {errors_count} validation errors",
            level="warning"
        )


# 7. Track session override writes
def breadcrumb_session_override(row_key):
    sentry_sdk.add_breadcrumb(
        category="session_override",
        message=f"Override saved for row_key={row_key}",
        level="info"
    )
