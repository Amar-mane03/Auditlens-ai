# AuditLens Fraud Intelligence & Autonomous ML Backend

The `auditlens_backend` service delivers production-grade enterprise fraud scoring, human-in-the-loop audit feedback learning, and MLOps model governance for the AuditLens Platform.

## Core Capabilities

1. **Autonomous ML Fraud Classification**:
   - Logistic regression model pipeline with feature scaling.
   - Evaluates risk score (0.00 – 1.00), prediction label (`fraud` vs. `legitimate`), and risk tiers (`low`, `medium`, `high`).
   - Automated case generation for high-risk predictions.

2. **Continuous Feedback Learning Loop**:
   - Captures human auditor dispositions (`confirmed_fraud`, `legitimate`, `inconclusive`).
   - Tracks verified outcomes and builds training-eligible feedback datasets.
   - Prevents data leakage with temporal splitting and validation checks.

3. **Champion-Challenger Model Governance**:
   - Evaluates candidate models against strict performance delta gates (Precision, Recall, PR-AUC).
   - Instant promotion to Champion or rollback to previous models with immutable audit trails.

4. **Forensic Analytics & Timeline Intelligence**:
   - Temporal aggregation across daily, weekly, and monthly trends.
   - Exposure tracking, recovered amounts, and dispute workflows.

## API Endpoints

- `GET /api/health` - Health check & database connection status.
- `POST /api/predictions` - Real-time ML fraud scoring.
- `GET /api/transactions` - Filtered transaction registry.
- `GET /api/fraud-cases` - Filtered investigation case registry.
- `POST /api/fraud-cases/{id}/start-review` - Assign and open case review.
- `POST /api/fraud-cases/{id}/resolve` - Resolve case with confirmed/recovered amounts.
- `GET /api/ml/metrics` - Active models, candidate performance, feedback counts.
- `POST /api/ml/training-jobs` - Trigger background retraining worker.
- `GET /api/ml/training-jobs/{id}` - Poll training job progress.
- `POST /api/ml/models/{version}/promote` - Promote candidate model to active Champion.
- `POST /api/ml/models/{version}/rollback` - Rollback to retained model.
