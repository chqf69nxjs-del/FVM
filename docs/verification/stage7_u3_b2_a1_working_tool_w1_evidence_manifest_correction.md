# Working Tool W1 artifact-manifest path correction

## Classification

```text
IMPLEMENTATION / BOOKKEEPING ISSUE
NO PHYSICS CHANGE
NO NUMERICAL CHANGE
NO PUBLIC OUTPUT CHANGE
```

## Observation

The first successful W1 CI run produced a valid artifact and a valid smoke-internal `artifact_sha256.txt`. However, the workflow-level `workflow_artifact_sha256.txt` recorded repository-relative paths beginning with:

```text
artifacts/u3-b2-a1-working-tool-w1/
```

GitHub artifact download strips that upload-root prefix. Therefore the recorded hashes are correct, but `sha256sum -c workflow_artifact_sha256.txt` cannot resolve the paths directly from the extracted artifact root.

## Correction

Generate the workflow-level manifest from inside the upload root so its paths are artifact-relative:

```text
./changed_paths.txt
./pytest.log
./smoke/...
```

## Preserved scope

The correction does not alter:

- Working Tool case, run, result, warning, transition, or output contracts;
- A2 live backend behavior;
- FvmSolver, EOS, B1/B2, manager, A1 composer, or Increment 9L delegates;
- smoke step count, starting state, model selection, fluxes, or state trajectory;
- public/verification output separation;
- any formal status or approval claim.

W1 remains incomplete until a clean rerun produces an artifact whose workflow-level and smoke-level manifests both verify from the extracted artifact roots.
