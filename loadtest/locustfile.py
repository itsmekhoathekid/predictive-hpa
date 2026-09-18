import os
import random

from locust import FastHttpUser, LoadTestShape, between, events, task


class StagedLoadShape(LoadTestShape):
    """Ramp demand through repeatable stages so the online model can observe a trend."""

    use_common_options = True
    maximum_users = int(os.getenv("LOCUST_USERS", "150"))
    spawn_rate = float(os.getenv("LOCUST_SPAWN_RATE", "25"))
    stage_targets = (
        (0.2, max(1, maximum_users // 4)),
        (0.4, max(1, maximum_users // 2)),
        (0.6, maximum_users),
        (0.8, max(1, maximum_users // 2)),
        (1.0, max(1, maximum_users // 4)),
    )

    def tick(self) -> tuple[int, float] | None:
        run_time = self.get_run_time()  # type: ignore[no-untyped-call]
        if self.runner is None:
            return None
        options = self.runner.environment.parsed_options
        configured_duration = options.run_time if options is not None else None
        total_duration = float(configured_duration or 300)
        for fraction, users in self.stage_targets:
            if run_time < total_duration * fraction:
                return users, self.spawn_rate
        return None


class HousePriceUser(FastHttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def predict_house_price(self) -> None:
        payload = {
            "transaction_date": random.uniform(2012.67, 2013.58),
            "house_age_years": random.uniform(0.0, 43.8),
            "distance_to_mrt_m": random.uniform(23.0, 6_488.0),
            "nearby_convenience_stores": random.randint(0, 10),
            "latitude": random.uniform(24.93, 25.01),
            "longitude": random.uniform(121.47, 121.57),
            "area_m2": random.uniform(30.0, 180.0),
        }
        with self.client.post(
            "/predict",
            json=payload,
            headers={"Connection": "close"} if random.random() < 0.05 else None,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status {response.status_code}")
                return
            body = response.json()
            if "estimated_total_price_twd" not in body:
                response.failure("prediction field is missing")


@events.quitting.add_listener  # type: ignore[untyped-decorator]
def set_exit_code(environment, **_kwargs) -> None:  # type: ignore[no-untyped-def]
    if environment.stats.total.fail_ratio >= 0.01:
        environment.process_exit_code = 1
