# Phase 4: Refactoring Plan for api/routes/ml.py

## Current State
- **File**: `api/routes/ml.py`
- **Lines**: 4,222
- **Routes**: 44 endpoints
- **Problem**: Monolithic file, hard to maintain

## Proposed Structure

Split into 6 focused modules:

### 1. `ml_dashboard.py` - Dashboard & Analytics (4 routes, ~400 lines)
- GET `/dashboard/stats` - ML dashboard statistics
- GET `/dashboard/data_quality` - Data quality metrics
- GET `/dashboard/ml_trades_count` - ML trades count
- GET `/exploratory/performance` - Performance analysis

**Purpose**: Read-only analytics and dashboard data

### 2. `ml_models.py` - Model Management (6 routes, ~700 lines)
- GET `/models/overview` - Model overview
- GET `/models/status` - Model status
- GET `/models/metrics/{model_name}` - Model metrics
- GET `/models/experiments` - Experiment history
- GET `/features/importance` - Feature importance
- GET `/features/correlation_matrix` - Correlation analysis

**Purpose**: Model inspection and feature analysis

### 3. `ml_predictions.py` - Predictions & Filtering (8 routes, ~600 lines)
- GET `/predictions/analytics` - Prediction analytics
- GET `/predictions/recent` - Recent predictions
- POST `/predictor/reload` - Reload predictor
- POST `/predict` - Single prediction (v1)
- POST `/predict/batch` - Batch prediction (v1)
- POST `/predict_v2` - Single prediction (v2)
- POST `/predict_v2/batch` - Batch prediction (v2)
- POST `/predict_v2/filter` - Filter setup with prediction

**Purpose**: Real-time predictions and filtering

### 4. `ml_training.py` - Training & Verification (7 routes, ~900 lines)
- GET `/retrain/check` - Check retrain status
- POST `/retrain` - Retrain model
- POST `/train` - Train model (v1)
- POST `/train_v2` - Train model (v2)
- POST `/train_gb` - Train gradient boosting
- POST `/verify_gb` - Verify GB model
- GET `/verify_gb/complete` - Complete verification

**Purpose**: Model training and verification workflows

### 5. `ml_optimization.py` - Hyperparameter Optimization (14 routes, ~1,500 lines)
- GET `/optimize/summary` - Optimization summary
- POST `/optimize/start` - Start optimization
- GET `/optimize/history` - Optimization history
- GET `/optimize/best` - Best parameters
- POST `/optimize/apply` - Apply parameters
- POST `/optimize/gb/start` - Start GB optimization
- POST `/optimize/gb/apply` - Apply GB parameters
- GET `/optimize/gb/results` - GB results
- POST `/optimize_v2/start` - Start optimization v2
- GET `/optimize_v2/status` - Optimization status v2
- POST `/optimize_v2/apply` - Apply parameters v2
- POST `/optimize_gb` - Optimize GB (single endpoint)
- GET `/optimize_gb/status` - GB optimization status
- POST `/optimize_gb/apply` - Apply GB optimization
- GET `/optimize_gb/history` - GB optimization history

**Purpose**: Hyperparameter tuning workflows

### 6. `ml_tasks.py` - Task Management & Alerts (4 routes, ~300 lines)
- GET `/tasks/{task_id}` - Get task status (plural)
- GET `/task/{task_id}` - Get task status (singular)
- GET `/alerts/history` - Alert history
- POST `/alerts/test` - Test alert

**Purpose**: Async task tracking and alerting

## Shared Dependencies

Create `ml_common.py` for shared utilities:
- Task store functions (`_get_task_from_store`, etc.)
- Metric cache functions (`_load_metric_runs_cache`, `_save_metric_runs_cache`)
- Common helpers (`_generate_recommendations`, etc.)
- Shared imports and configurations

## Migration Steps

1. ✅ Create PHASE4_ML_SPLIT_PLAN.md (this file)
2. Create `api/routes/ml_common.py` with shared utilities
3. Create 6 new module files with appropriate imports
4. Migrate routes category by category (start with smallest)
5. Update `main.py` to include all 6 routers
6. Test each module independently
7. Remove original `ml.py` file
8. Update documentation

## Benefits

- **Maintainability**: Each file ~300-900 lines (manageable size)
- **Clarity**: Clear separation of concerns
- **Performance**: Faster file navigation and IDE performance
- **Team Collaboration**: Reduced merge conflicts
- **Testing**: Easier to test individual modules
- **Discovery**: Easier to find specific functionality

## Backward Compatibility

All routes maintain the same paths - no breaking changes.
The split is purely organizational.

## Estimated Impact

- Current: 1 file × 4,222 lines = hard to navigate
- After: 7 files × ~600 lines avg = easy to navigate
- Lines per file reduction: 85% improvement
- File navigation time: ~80% faster

## Testing Strategy

1. Verify all 44 routes still respond correctly
2. Check import chains don't create circular dependencies
3. Validate shared utilities work from all modules
4. Ensure no routes are duplicated or missing
