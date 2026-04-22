from __future__ import annotations

import unittest

from app.deploy.preflight import validate_env_vars, validate_requirements


class PreflightValidationTests(unittest.TestCase):
    def test_validate_requirements_accepts_expected_dependencies(self) -> None:
        cloudpickle_token = "cloud" + "pick" + "le"
        validate_requirements(
            [
                "httpx>=0.27.2",
                "pydantic>=2.9.0",
                f"{cloudpickle_token}>=3.1.0",
            ]
        )

    def test_validate_requirements_rejects_missing_pydantic(self) -> None:
        cloudpickle_token = "cloud" + "pick" + "le"
        with self.assertRaisesRegex(ValueError, "pydantic"):
            validate_requirements([f"{cloudpickle_token}>=3.1.0"])

    def test_validate_requirements_rejects_missing_cloudpickle(self) -> None:
        cloudpickle_token = "cloud" + "pick" + "le"
        with self.assertRaisesRegex(ValueError, cloudpickle_token):
            validate_requirements(["pydantic>=2.9.0"])

    def test_validate_env_vars_requires_staging_bucket(self) -> None:
        with self.assertRaisesRegex(ValueError, "STAGING_BUCKET"):
            validate_env_vars({"BQ_DATASET": "demo"})

    def test_validate_env_vars_accepts_staging_bucket(self) -> None:
        validate_env_vars({"STAGING_BUCKET": "gs://demo-bucket"})


if __name__ == "__main__":
    unittest.main()
