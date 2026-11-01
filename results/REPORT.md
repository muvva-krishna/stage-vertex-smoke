# Debugging-evidence pilot report

> Small pilot: per-task outcomes and raw attempt counts only. Do not claim population-level conclusions or statistical significance from this sample.

Total runs: 5

Packet sizes differ by condition by design (combined carries more);
read pass rates as 'which realistic packet works best', not as
evidence-type attribution. See `evidence_tokens` per cell.

## Outcomes by task x condition

| task | condition | attempts | passes | pass_rate | totals | evid_tokens | replayed |
|---|---|---|---|---|---|---|---|
| migration-resume | code_note | 1 | 1 | 1.0 | [77.5] | [79] | False |
| migration-resume | combined | 1 | 1 | 1.0 | [77.5] | [190] | False |
| migration-resume | repro_log | 1 | 1 | 1.0 | [77.5] | [88] | False |
| migration-resume | state_snapshot | 1 | 0 | 0.0 | [62.5] | [87] | False |
| migration-resume | symptom_only | 1 | 1 | 1.0 | [77.5] | [32] | False |

## Runs (trajectory summaries + failure labels)

### muse-spark-1-3-contributor-slot-01-code_note-r04 (migration-resume / code_note)
- runner: ./agents/muse_spark_contributor.py:MuseSparkContributorRunner; isolation: bwrap-sandbox; commit: 1b5fc09e658e023fdd86fbc7855d02e3db898a07
- human grade: PENDING (not a zero)
- events: 13; evidence opened: ['code_note.md', 'symptom.md']
- tests: [{'seq': 8, 'name': 'public-unittest-suite', 'result': 'PASS'}]
- files changed: ['debev_config/migration.py']
- score: {'task_id': 'migration-resume', 'condition': 'code_note', 'run_id': 'muse-spark-1-3-contributor-slot-01-code_note-r04', 'components': [{'component': 'functional_correctness', 'points': 50.0, 'max_points': 50, 'grade_mode': 'machine', 'detail': 'fresh_migration=PASS; resume_committed_target=PASS; resume_partial_target=PASS; completed_idempotence=PASS'}, {'component': 'root_cause_diagnosis', 'points': 0.0, 'max_points': 20, 'grade_mode': 'human', 'detail': 'PENDING HUMAN GRADE (placeholder)'}, {'component': 'compatibility_regression', 'points': 15.0, 'max_points': 15, 'grade_mode': 'machine', 'detail': 'cli=PASS'}, {'component': 'constraint_compliance', 'points': 10.0, 'max_points': 10, 'grade_mode': 'machine', 'detail': 'no_evaluator_files_in_workspace=PASS; no_reference_patch_file=PASS'}, {'component': 'verification_reporting', 'points': 2.5, 'max_points': 5, 'grade_mode': 'mixed', 'detail': 'machine portion: structured agent verification observed (verification event or test_run with a verdict; oracle run excluded)'}], 'total': 77.5, 'passed': True}
- efficiency: {'tool_calls': 4, 'tests_run': 1, 'verifications': 0, 'evidence_tokens': 79, 'model_tokens': None, 'wall_clock_s': 60.99, 'retries': 0}

### muse-spark-1-3-contributor-slot-01-combined-r03 (migration-resume / combined)
- runner: ./agents/muse_spark_contributor.py:MuseSparkContributorRunner; isolation: bwrap-sandbox; commit: 1b5fc09e658e023fdd86fbc7855d02e3db898a07
- human grade: PENDING (not a zero)
- events: 15; evidence opened: ['code_note.md', 'repro_log.md', 'state_snapshot.md', 'symptom.md']
- tests: [{'seq': 10, 'name': 'public-unittest-suite', 'result': 'PASS'}]
- files changed: ['debev_config/migration.py']
- score: {'task_id': 'migration-resume', 'condition': 'combined', 'run_id': 'muse-spark-1-3-contributor-slot-01-combined-r03', 'components': [{'component': 'functional_correctness', 'points': 50.0, 'max_points': 50, 'grade_mode': 'machine', 'detail': 'fresh_migration=PASS; resume_committed_target=PASS; resume_partial_target=PASS; completed_idempotence=PASS'}, {'component': 'root_cause_diagnosis', 'points': 0.0, 'max_points': 20, 'grade_mode': 'human', 'detail': 'PENDING HUMAN GRADE (placeholder)'}, {'component': 'compatibility_regression', 'points': 15.0, 'max_points': 15, 'grade_mode': 'machine', 'detail': 'cli=PASS'}, {'component': 'constraint_compliance', 'points': 10.0, 'max_points': 10, 'grade_mode': 'machine', 'detail': 'no_evaluator_files_in_workspace=PASS; no_reference_patch_file=PASS'}, {'component': 'verification_reporting', 'points': 2.5, 'max_points': 5, 'grade_mode': 'mixed', 'detail': 'machine portion: structured agent verification observed (verification event or test_run with a verdict; oracle run excluded)'}], 'total': 77.5, 'passed': True}
- efficiency: {'tool_calls': 4, 'tests_run': 1, 'verifications': 0, 'evidence_tokens': 190, 'model_tokens': None, 'wall_clock_s': 42.18, 'retries': 0}

### muse-spark-1-3-contributor-slot-01-repro_log-r01 (migration-resume / repro_log)
- runner: ./agents/muse_spark_contributor.py:MuseSparkContributorRunner; isolation: bwrap-sandbox; commit: 1b5fc09e658e023fdd86fbc7855d02e3db898a07
- human grade: PENDING (not a zero)
- events: 13; evidence opened: ['repro_log.md', 'symptom.md']
- tests: [{'seq': 8, 'name': 'public-unittest-suite', 'result': 'PASS'}]
- files changed: ['debev_config/migration.py']
- score: {'task_id': 'migration-resume', 'condition': 'repro_log', 'run_id': 'muse-spark-1-3-contributor-slot-01-repro_log-r01', 'components': [{'component': 'functional_correctness', 'points': 50.0, 'max_points': 50, 'grade_mode': 'machine', 'detail': 'fresh_migration=PASS; resume_committed_target=PASS; resume_partial_target=PASS; completed_idempotence=PASS'}, {'component': 'root_cause_diagnosis', 'points': 0.0, 'max_points': 20, 'grade_mode': 'human', 'detail': 'PENDING HUMAN GRADE (placeholder)'}, {'component': 'compatibility_regression', 'points': 15.0, 'max_points': 15, 'grade_mode': 'machine', 'detail': 'cli=PASS'}, {'component': 'constraint_compliance', 'points': 10.0, 'max_points': 10, 'grade_mode': 'machine', 'detail': 'no_evaluator_files_in_workspace=PASS; no_reference_patch_file=PASS'}, {'component': 'verification_reporting', 'points': 2.5, 'max_points': 5, 'grade_mode': 'mixed', 'detail': 'machine portion: structured agent verification observed (verification event or test_run with a verdict; oracle run excluded)'}], 'total': 77.5, 'passed': True}
- efficiency: {'tool_calls': 4, 'tests_run': 1, 'verifications': 0, 'evidence_tokens': 88, 'model_tokens': None, 'wall_clock_s': 99.0, 'retries': 0}

### muse-spark-1-3-contributor-slot-01-state_snapshot-r00 (migration-resume / state_snapshot)
- runner: ./agents/muse_spark_contributor.py:MuseSparkContributorRunner; isolation: bwrap-sandbox; commit: 1b5fc09e658e023fdd86fbc7855d02e3db898a07
- human grade: PENDING (not a zero)
- events: 13; evidence opened: ['state_snapshot.md', 'symptom.md']
- tests: [{'seq': 8, 'name': 'public-unittest-suite', 'result': 'PASS'}]
- files changed: ['debev_config/migration.py']
- score: {'task_id': 'migration-resume', 'condition': 'state_snapshot', 'run_id': 'muse-spark-1-3-contributor-slot-01-state_snapshot-r00', 'components': [{'component': 'functional_correctness', 'points': 35.0, 'max_points': 50, 'grade_mode': 'machine', 'detail': 'fresh_migration=PASS; resume_committed_target=PASS; resume_partial_target=FAIL; completed_idempotence=PASS'}, {'component': 'root_cause_diagnosis', 'points': 0.0, 'max_points': 20, 'grade_mode': 'human', 'detail': 'PENDING HUMAN GRADE (placeholder)'}, {'component': 'compatibility_regression', 'points': 15.0, 'max_points': 15, 'grade_mode': 'machine', 'detail': 'cli=PASS'}, {'component': 'constraint_compliance', 'points': 10.0, 'max_points': 10, 'grade_mode': 'machine', 'detail': 'no_evaluator_files_in_workspace=PASS; no_reference_patch_file=PASS'}, {'component': 'verification_reporting', 'points': 2.5, 'max_points': 5, 'grade_mode': 'mixed', 'detail': 'machine portion: structured agent verification observed (verification event or test_run with a verdict; oracle run excluded)'}], 'total': 62.5, 'passed': False}
- efficiency: {'tool_calls': 4, 'tests_run': 1, 'verifications': 0, 'evidence_tokens': 87, 'model_tokens': None, 'wall_clock_s': 48.3, 'retries': 0}

### muse-spark-1-3-contributor-slot-01-symptom_only-r02 (migration-resume / symptom_only)
- runner: ./agents/muse_spark_contributor.py:MuseSparkContributorRunner; isolation: bwrap-sandbox; commit: 1b5fc09e658e023fdd86fbc7855d02e3db898a07
- human grade: PENDING (not a zero)
- events: 12; evidence opened: ['symptom.md']
- tests: [{'seq': 7, 'name': 'public-unittest-suite', 'result': 'PASS'}]
- files changed: ['debev_config/migration.py']
- score: {'task_id': 'migration-resume', 'condition': 'symptom_only', 'run_id': 'muse-spark-1-3-contributor-slot-01-symptom_only-r02', 'components': [{'component': 'functional_correctness', 'points': 50.0, 'max_points': 50, 'grade_mode': 'machine', 'detail': 'fresh_migration=PASS; resume_committed_target=PASS; resume_partial_target=PASS; completed_idempotence=PASS'}, {'component': 'root_cause_diagnosis', 'points': 0.0, 'max_points': 20, 'grade_mode': 'human', 'detail': 'PENDING HUMAN GRADE (placeholder)'}, {'component': 'compatibility_regression', 'points': 15.0, 'max_points': 15, 'grade_mode': 'machine', 'detail': 'cli=PASS'}, {'component': 'constraint_compliance', 'points': 10.0, 'max_points': 10, 'grade_mode': 'machine', 'detail': 'no_evaluator_files_in_workspace=PASS; no_reference_patch_file=PASS'}, {'component': 'verification_reporting', 'points': 2.5, 'max_points': 5, 'grade_mode': 'mixed', 'detail': 'machine portion: structured agent verification observed (verification event or test_run with a verdict; oracle run excluded)'}], 'total': 77.5, 'passed': True}
- efficiency: {'tool_calls': 4, 'tests_run': 1, 'verifications': 0, 'evidence_tokens': 32, 'model_tokens': None, 'wall_clock_s': 47.1, 'retries': 0}
