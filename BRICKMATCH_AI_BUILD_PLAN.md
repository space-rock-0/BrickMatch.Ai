# BrickMatch AI 

**Project:** Personalized Multimodal LEGO Recommendation Engine\
**Purpose:** Build a credible, reproducible ML engineering portfolio
project\
**Primary development environment:** Windows 10/11, Python 3.11,
CPU-first\
**Target hardware:** 8 GB RAM laptop; no dedicated GPU required\
------------------------------------------------------------------------

## 0. Executive decision

Build **BrickMatch AI**, a local-first recommendation product that
learns a user's LEGO preferences from explicit likes and dislikes,
combines image and catalog metadata, retrieves candidate sets
efficiently, ranks them, and explains recommendations.

The project must demonstrate more than a working UI. Its strongest
evidence should be:

1.  A reproducible data ingestion and image-processing pipeline.
2.  Reusable CLIP image embeddings with stable set-ID mapping.
3.  Well-defined recommendation baselines and a hybrid ranking model.
4.  Leakage-safe offline evaluation with honest metrics.
5.  Feedback persistence and controlled model updates.
6.  A tested API and usable interactive application.
7.  Versioned datasets, features, indexes, and models.
8.  Automated tests, reproducible runs, documentation, and a
    demonstrable deployment.

**Do not start by building the complete application in one prompt.**
Build one phase at a time. Every phase must have a clear deliverable,
tests, and a completion gate.

### Scope boundary

This is a **small production-style portfolio system**, not an
enterprise-scale recommender. Do not add Kubernetes, Kafka, distributed
training, microservices, a feature store, or cloud GPU infrastructure
unless a measured requirement justifies them.

------------------------------------------------------------------------

## 1. Product requirements

### 1.1 Primary user journey

1.  A user opens BrickMatch AI.
2.  The user browses a catalog of LEGO sets.
3.  The user likes, dislikes, skips, or changes a previous rating.
4.  The application stores feedback with a timestamp and user ID.
5.  The system builds or updates that user's preference profile.
6.  The recommendation service retrieves eligible unseen sets.
7.  A ranking model scores the candidates.
8.  The application displays a ranked list with concise, evidence-based
    explanations.
9.  The user can inspect why an item was recommended and provide more
    feedback.
10. The evaluation area displays measured offline model performance and
    system health.

### 1.2 Functional requirements

-   Browse and search LEGO sets.
-   Filter by available metadata such as theme, year, and piece count. select age group select  theme  or genre 
-   Display set images with a safe fallback when images are unavailable.
-   Record `like`, `dislike`, and `skip` actions.
-   Allow a user to correct or undo feedback.
-   Keep users' feedback and recommendations isolated.
-   Exclude already-rated sets from normal recommendations.
-   Provide recommendations for new users through a cold-start fallback.
-   Provide recommendations when a user has too little feedback to train
    a classifier.
-   Generate top-K recommendations with deterministic tie-breaking.
-   Explain recommendations using actual model signals, not invented
    natural-language claims.
-   Expose model version, feature version, and generation time.
-   Provide an admin/developer view of data, evaluation, and model
    status.

### 1.3 Non-functional requirements

-   Runs locally on Windows without requiring a GPU.
-   Uses bounded memory and batch processing.
-   Can resume or safely repeat data ingestion.
-   Does not regenerate embeddings when source images and model
    configuration have not changed.
-   Uses typed API schemas and clear error responses.
-   Has automated tests for critical ML and application behavior.
-   Keeps secrets and local user data out of Git.
-   Can be installed from documented instructions on a second machine.
-   Does not claim performance or accuracy values that have not been
    measured.

### 1.4 Explicit non-goals for version 1

-   Training CLIP from scratch.
-   Real-time retraining after every swipe.
-   Collaborative filtering requiring a large population of real users.
-   Paid recommendation APIs.
-   Product checkout or LEGO purchasing.
-   Scraping sites in ways that violate terms.
-   Cloud deployment as a prerequisite for project completion.
-   LLM-generated recommendation explanations.

------------------------------------------------------------------------

## 2. Architecture

### 2.1 High-level architecture

``` mermaid
flowchart TD
    A[Rebrickable catalog data] --> B[Ingestion and validation]
    I[Permitted set image sources] --> B
    B --> C[Canonical catalog and image manifest]
    C --> D[Image preprocessing]
    D --> E[Pretrained CLIP encoder]
    E --> F[Versioned image embeddings]
    C --> G[Metadata preprocessing]
    G --> H[Versioned metadata features]
    F --> J[FAISS visual index]
    F --> K[Hybrid feature builder]
    H --> K
    L[User feedback database] --> M[User profile and training data]
    K --> N[Candidate retrieval and ranking]
    J --> N
    M --> N
    N --> O[Recommendation API]
    O --> P[Streamlit application]
    M --> Q[Training and evaluation pipeline]
    K --> Q
    Q --> R[Model evaluation and promotion]
    R --> S[Versioned model artifacts]
    S --> N
    T[Logs, metrics, tests] --> U[Monitoring and reports]
```

### 2.2 Architectural principles

-   **Offline/online separation:** catalog ingestion, image embedding
    generation, training, and evaluation are offline jobs.
    Recommendation requests should load existing artifacts and perform
    bounded retrieval and ranking.
-   **Stable identity:** every catalog record, image embedding, feature
    row, and recommendation must map to a canonical `set_id`.
-   **Version everything:** record data version, image hash, CLIP model
    identifier, preprocessing version, feature schema version, FAISS
    index version, and classifier version.
-   **Reproducibility:** all training and evaluation runs must be
    configured and logged.
-   **Small modular monolith:** one backend application with clear
    modules is preferable to multiple services for this project.
-   **Graceful fallback:** if FAISS cannot be installed on the Windows
    environment, provide a tested scikit-learn nearest-neighbor backend
    behind the same retrieval interface.
-   **Local-first:** SQLite is sufficient initially. PostgreSQL is an
    optional later migration, not a blocker.

### 2.3 Request-time recommendation flow

1.  Validate user ID and request parameters.
2.  Load the user's current feedback/profile.
3.  Select the active model and feature versions.
4.  Build a query profile from liked and disliked items.
5.  Retrieve a candidate pool using FAISS or the fallback retriever.
6.  Remove unavailable, duplicate, and already-rated sets.
7.  Build hybrid candidate features.
8.  Score candidates with the user's classifier if it is valid;
    otherwise use a documented fallback.
9.  Apply ranking and diversity constraints.
10. Return top K with score components, model version, and explanations.
11. Record recommendation impressions if implementing exposure-aware
    evaluation.

------------------------------------------------------------------------

## 3. Technology decisions

  -----------------------------------------------------------------------
  Area                    Selected technology     Reason / constraint
  ----------------------- ----------------------- -----------------------
  Language                Python 3.11             Broad ML ecosystem

  Environment             `venv`                  Simple Windows-native
                                                  workflow

  Data                    Rebrickable             Catalog metadata
                          downloadable data/API   
                          where permitted         

  Data processing         Pandas, NumPy           Tabular and vector
                                                  processing

  Images                  Pillow, `requests` or   Download and validate
                          `httpx`                 images

  Vision model            OpenAI CLIP ViT-B/32    Pretrained visual
                          via Transformers or     representation
                          OpenCLIP                

  ML framework            PyTorch CPU             Run pretrained encoder

  Classifier              scikit-learn            Interpretable baseline
                          LogisticRegression      preference model

  Preprocessing           `ColumnTransformer`,    Mixed metadata features
                          `OneHotEncoder`,        
                          `StandardScaler`        

  Vector search           FAISS CPU where         Approximate/exact
                          supported               vector retrieval

  Fallback retrieval      scikit-learn            Windows compatibility
                          NearestNeighbors        fallback

  Backend                 FastAPI + Pydantic      Typed REST API

  Frontend                Streamlit               Fast, interactive demo

  Initial database        SQLite                  Low resource use and
                                                  easy local setup

  Optional database       PostgreSQL              Later
                                                  deployment/multi-user
                                                  exercise

  Experiment tracking     MLflow                  Run and metric tracking

  Tests                   pytest                  Unit, integration, and
                                                  API tests

  API test client         FastAPI                 Endpoint tests
                          TestClient/httpx        

  Packaging               Docker optional         Reproducible runtime

  CI                      GitHub Actions          Automated tests and
                                                  linting

  Lint/format             Ruff                    Fast Python code
                                                  quality

  Monitoring              Structured logs +       Appropriate scale
                          lightweight metrics     

  Documentation           Markdown + Mermaid      Architecture and
                                                  reproducibility
  -----------------------------------------------------------------------

### 3.1 Hardware-aware constraints

The target laptop has approximately 8 GB RAM. Confirm exact hardware and
free disk before implementation.

-   Start with 500--1,000 catalog sets.
-   Process images in batches of 1--4 initially; increase only after
    measuring memory.
-   Run CLIP on CPU initially.
-   Resize images to the model's required input size through its
    official processor.
-   Do not hold all decoded images in memory.
-   Save embeddings incrementally.
-   Use `float32` for compatibility; test `float16` storage only if it
    preserves retrieval quality and is supported safely.
-   Load the CLIP model only in the offline embedding job, not in the
    API request path.
-   Avoid running model training, embedding generation, and the full UI
    simultaneously on 8 GB RAM.
-   Keep the raw image collection and model artifacts outside Git.
-   Measure actual disk use and runtime before increasing catalog size.

### 3.2 Installation compatibility gate

Before committing to FAISS, Docker, or a database, test installation on
the actual Windows machine.

-   Create a clean Python 3.11 virtual environment.
-   Install PyTorch CPU and the chosen CLIP stack.
-   Run one image through the encoder.
-   Verify embedding shape and finite values.
-   Attempt the intended FAISS CPU installation.
-   If it fails, use the tested nearest-neighbor fallback and document
    the reason.
-   Docker Desktop is optional and must not block local development.

Do not switch to WSL2 merely to avoid understanding a package issue.
First test Windows-native options and document any platform limitation.

------------------------------------------------------------------------

## 4. Data sourcing and governance

### 4.1 Source strategy

Use Rebrickable's downloadable catalog data as the initial source of set
and theme metadata. Use its API only where needed and within its
terms/rate limits. Verify the current downloadable fields and API
response schema before writing ingestion code.

Do not assume every dataset file contains image URLs, prices,
popularity, or user ratings. Inspect the actual source files and
document field availability.

Potential catalog fields include:

-   Set identifier
-   Set name
-   Year
-   Theme identifier
-   Number of parts

Additional attributes such as image URL, price, availability, or
popularity must be included only when a permitted, reliable source
provides them.

### 4.2 Image source policy

-   Use image URLs or assets that are permitted by the source's terms.
-   Record the original image source and retrieval timestamp.
-   Do not bypass access controls or scrape against site terms.
-   Do not redistribute catalog images in the public repository unless
    the license permits it.
-   Store local image paths and hashes in a manifest.
-   Use a placeholder in the UI when an image is missing.
-   Make the demo's image usage and attribution clear.

### 4.3 Raw and processed data layout

``` text
data/
  raw/
    rebrickable/
    image_manifest/
  interim/
    validated_catalog/
    downloaded_images/
  processed/
    catalog.parquet
    image_manifest.parquet
    metadata_features/
  splits/
    train_feedback.parquet
    validation_feedback.parquet
    test_feedback.parquet
```

Raw data must be immutable. Re-running ingestion should create or update
a versioned processed dataset, not silently rewrite the source.

### 4.4 Data validation

Validate:

-   Unique and non-empty set IDs.
-   Valid theme references.
-   Valid year and piece-count ranges.
-   Missing-value rates.
-   Image URL format and response status.
-   Image decodability and dimensions.
-   Duplicate image hashes.
-   Image-to-set mapping completeness.
-   Feature-row-to-set mapping completeness.

Produce a data quality report with counts, missingness, rejected
records, and reasons.

### 4.5 Ingestion reliability

-   Use request timeouts.
-   Retry transient network errors with bounded exponential backoff.
-   Do not retry permanent 404 responses indefinitely.
-   Use a bounded number of concurrent downloads.
-   Write downloads to temporary files and atomically rename after
    validation.
-   Store status per image: pending, downloaded, missing, failed,
    invalid.
-   Resume from the manifest.
-   Respect API limits and source terms.

**Phase deliverable:** a reproducible catalog and image manifest with a
data-quality report.

------------------------------------------------------------------------

## 5. Feature engineering and CLIP embeddings

### 5.1 Image embedding pipeline

1.  Read the canonical catalog.
2.  Resolve the permitted image for each set.
3.  Validate and decode the image.
4.  Apply the exact preprocessing expected by the selected CLIP
    checkpoint.
5.  Run the image encoder in small batches.
6.  Normalize embeddings for cosine similarity.
7.  Save vectors and the matching ordered set-ID array.
8.  Save metadata describing the encoder and preprocessing.
9.  Resume safely after interruption.

For CLIP ViT-B/32, the image embedding is commonly 512 dimensions.
Verify the actual output shape from the loaded model rather than
hard-coding an assumption without a test.

### 5.2 Embedding artifacts

``` text
artifacts/
  embeddings/
    clip_vit_b32/
      embeddings.npy
      set_ids.npy
      manifest.json
```

The manifest should contain:

-   Model repository/checkpoint and revision where available.
-   Processor/preprocessing configuration.
-   Embedding dimension.
-   Normalization method.
-   Data version.
-   Image-manifest version.
-   Number of successful embeddings.
-   Failed set IDs.
-   Creation timestamp.
-   Code/config version.

### 5.3 Embedding integrity tests

-   Embedding row count equals set-ID count.
-   Set IDs are unique.
-   Every vector contains finite values.
-   Vector dimension matches the model.
-   Normalized vector norms are approximately one.
-   Each vector maps to the correct catalog set.
-   Re-running the same pipeline with unchanged inputs produces
    equivalent embeddings within a documented tolerance.

### 5.4 Metadata features

Separate features into appropriate types:

**Categorical** - Theme or theme hierarchy where available.

**Numerical** - Number of parts. - Release year. - Price only if
obtained from a reliable and permitted source.

**Derived** - Set age relative to a fixed evaluation/reference date, if
useful. - Log-transformed piece count if its distribution is highly
skewed.

Preprocessing must be fitted on training data only and reused unchanged
for validation, test, and inference.

### 5.5 Feature representation experiments

Compare at least:

1.  CLIP visual features only.
2.  Metadata features only.
3.  Combined visual + metadata features.

Do not assume concatenating raw 512-dimensional CLIP vectors with
metadata is automatically optimal. Scale/encode metadata correctly and
compare alternatives on validation data.

**Phase deliverable:** cached image embeddings, a versioned metadata
feature pipeline, and tests proving the mappings are correct.

------------------------------------------------------------------------

## 6. Recommendation strategies and model design

Implement models incrementally. Every model must have a clear purpose
and a common evaluation interface.

### 6.1 Baseline A --- Popularity or catalog baseline

Use a legitimate popularity/rating field only if one exists in the
selected source. If it does not, define a transparent fallback such as
deterministic catalog ordering or a non-personalized curated baseline.
Do not invent popularity values.

Purpose: establish a non-personalized reference.

### 6.2 Baseline B --- Content-based visual retrieval

-   Normalize CLIP vectors.
-   Build a FAISS index over catalog embeddings.
-   Build a user query vector from liked item embeddings.
-   Retrieve nearest candidates.
-   Consider disliked items as a negative signal in a separately tested
    variant.
-   Exclude already-rated sets.

For normalized vectors, inner-product search corresponds to cosine
similarity. Test this property and document index metric and
normalization.

### 6.3 Baseline C --- Metadata similarity

Build a metadata-only retrieval baseline using a documented similarity
or distance function. This reveals whether metadata alone is useful.

### 6.4 Model D --- Personalized Logistic Regression

Train a per-user binary classifier only when there are enough labeled
examples and both classes are represented.

-   Target: like = 1, dislike = 0.
-   Input: versioned visual and metadata features.
-   Use regularization.
-   Tune hyperparameters using validation data only.
-   Handle class imbalance only when justified by the observed training
    distribution.
-   Calibrate probabilities only if the evaluation supports it.
-   Persist preprocessing and classifier together.
-   Record the feedback cutoff used to train the model.

Important limitation: a per-user classifier trained on a handful of
ratings is unstable. Do not force it to train with insufficient data.
Use a preference-profile fallback until the configured minimum evidence
is met.

### 6.5 Cold-start and low-feedback fallback

For a user with no or few ratings:

-   Offer onboarding choices or a small initial swipe session.
-   Use selected themes or liked examples to build a preference profile.
-   Use visual and metadata similarity.
-   Optionally blend a non-personalized baseline.
-   Clearly label the system as using a cold-start fallback.

Do not pretend the personalized classifier is trained when it is not.

### 6.6 Hybrid candidate retrieval and ranking

Recommended two-stage design:

**Stage 1 --- Candidate generation** - Retrieve a candidate pool from
visual similarity. - Optionally retrieve a pool from metadata
similarity. - Merge and deduplicate candidate IDs. - Keep retrieval
source and retrieval score.

**Stage 2 --- Ranking** - Score candidates with a valid user classifier
when available. - Otherwise use a documented profile-similarity
fallback. - Add validated metadata compatibility signals. - Apply
exclusions and diversity rules. - Return top K.

A weighted score can be used as an initial transparent ranking baseline:

`final_score = alpha * preference_score + beta * visual_similarity + gamma * metadata_similarity`

Weights must be selected using validation experiments, not chosen after
inspecting test results. Keep component scores in the response for
debugging and explanations.

### 6.7 Diversity and business rules

-   Exclude sets already rated by the user.
-   Avoid duplicate set IDs.
-   Optionally cap the number of items from one theme in top K.
-   Compare ranking with and without diversity reranking.
-   Measure diversity and coverage; do not assume diversity improves
    user satisfaction.
-   Make diversity settings configurable and testable.

### 6.8 Recommendation explanations

Generate explanations from recorded evidence, for example:

-   Similar visual features to a set the user liked.
-   Matches a theme the user frequently likes.
-   Similar piece-count range to previously liked sets.

Do not use an LLM to invent explanations. Explanations should be
traceable to actual feature signals and preference history.

**Phase deliverable:** a common recommendation interface with baselines,
personalized model, cold-start fallback, and hybrid ranking.

------------------------------------------------------------------------

## 7. Feedback lifecycle and model updates

### 7.1 Feedback schema

Each feedback event should record:

-   Event ID.
-   User ID.
-   Set ID.
-   Action: like, dislike, skip, undo, or correction.
-   Event timestamp.
-   Optional recommendation/impression ID.
-   Application version.

Keep an immutable event history if feasible. Maintain a current-rating
view for simple training and filtering.

### 7.2 Training policy

Do not retrain on every swipe.

-   Persist feedback immediately.
-   Trigger training only after a configurable number of new valid
    ratings or an explicit developer action.
-   Train a candidate model separately.
-   Evaluate it against the current model on a fixed validation
    protocol.
-   Promote only if it meets the promotion policy.
-   Keep the previous valid artifact for rollback.
-   Record why a model was promoted or rejected.

### 7.3 Multi-user isolation

-   User A's feedback must not affect User B's personal model unless
    collaborative learning is explicitly added.
-   Scope database queries by user ID.
-   Test isolation at service and API levels.
-   Never use a global in-memory preference variable shared across
    requests.

### 7.4 Retraining and evaluation caveat

A user's historical test ratings must not leak into training. For a
temporal simulation, train using interactions available before a cutoff
and evaluate on later interactions. After evaluation is complete, a
separate final model may be trained on all eligible historical feedback
for demonstration, but the reported test metric must remain from the
untouched evaluation protocol.

**Phase deliverable:** reliable feedback persistence, a controlled
retraining command, model promotion rules, and multi-user isolation
tests.

------------------------------------------------------------------------

## 8. Evaluation methodology

This is a core project deliverable, not an optional dashboard feature.

### 8.1 Evaluation questions

-   Does personalization outperform non-personalized baselines?
-   Does visual similarity add value beyond metadata?
-   Does metadata add value beyond visual similarity?
-   Does hybrid ranking improve ranking quality?
-   How does quality change as feedback increases?
-   Does candidate retrieval find relevant items before ranking?
-   Does diversity reranking change catalog coverage and relevance?
-   How long does embedding generation take on the target laptop?
-   What is recommendation API latency at the chosen catalog size?

### 8.2 Metrics

  -----------------------------------------------------------------------
  Metric                              Definition / use
  ----------------------------------- -----------------------------------
  Precision@K                         Relevant recommended items divided
                                      by K

  Recall@K                            Relevant held-out items retrieved
                                      divided by relevant held-out items

  NDCG@K                              Ranking quality with higher weight
                                      for relevant items near the top

  Hit Rate@K                          Whether at least one relevant
                                      held-out item appears in top K

  Catalog coverage                    Fraction of eligible catalog items
                                      recommended

  Intra-list diversity                Average dissimilarity among
                                      recommended items

  Candidate recall                    Fraction of relevant items present
                                      in the retrieved candidate pool

  Inference latency                   Time to produce recommendations
                                      under a documented setup

  Embedding throughput                Images processed per unit time
  -----------------------------------------------------------------------

Define relevance before running experiments. For explicit binary
ratings, document whether only likes count as relevant and how dislikes
are treated. Skips and unseen items must not automatically be treated as
dislikes.

### 8.3 Split strategy

Use a temporal split for a user's interactions when timestamps are
available:

-   Earlier feedback: training.
-   Later feedback: validation.
-   Latest held-out feedback: test.

For multiple users, report both: - Per-user personalization evaluation
where each user has enough interactions. - User-level generalization
only if the system is actually designed and trained for that task.

Do not randomly split individual rows in a way that leaks future
interactions or duplicates across sets.

### 8.4 Small-data limitation

A single developer's ratings are not enough for broad claims about all
LEGO fans. Label results accurately as a personal or small pilot
dataset. If testers are recruited, obtain consent and report the number
of users and interactions. Do not fabricate feedback.

### 8.5 Experiment matrix

  -----------------------------------------------------------------------
  Experiment              Features / method       Purpose
  ----------------------- ----------------------- -----------------------
  E1                      Non-personalized        Reference
                          baseline                

  E2                      CLIP visual similarity  Visual value

  E3                      Metadata similarity     Metadata value

  E4                      Logistic Regression on  Visual preference
                          visual features         prediction

  E5                      Logistic Regression on  Metadata preference
                          metadata features       prediction

  E6                      Combined visual +       Feature fusion
                          metadata classifier     

  E7                      Hybrid retrieval +      Full system
                          ranking                 

  E8                      Hybrid with diversity   Diversity trade-off
                          reranking               

  E9                      Feedback-size learning  Cold-start/data
                          curve                   efficiency
  -----------------------------------------------------------------------

### 8.6 Statistical honesty

-   Fix random seeds where applicable.
-   Repeat experiments where the split or sampling is stochastic.
-   Report sample sizes.
-   Include confidence intervals or variability when feasible.
-   Do not select the best test result by repeatedly changing the model.
-   Keep a final untouched test set.
-   Report negative results and limitations.
-   Never place illustrative or fabricated metrics in the README or
    resume.

### 8.7 Required evaluation artifacts

``` text
experiments/
  configs/
  runs/
  results/
    baseline_comparison.csv
    learning_curve.csv
    retrieval_evaluation.csv
    latency_benchmark.csv
  reports/
    evaluation_report.md
    plots/
```

**Phase deliverable:** a reproducible evaluation report with baseline
comparisons and honest limitations.

------------------------------------------------------------------------

## 9. Backend and API design

### 9.1 API structure

Prefix all endpoints with `/api/v1`.

  ------------------------------------------------------------------------------------
  Method                  Endpoint                             Purpose
  ----------------------- ------------------------------------ -----------------------
  GET                     `/sets`                              Search and paginate
                                                               catalog

  GET                     `/sets/{set_id}`                     Retrieve set details

  POST                    `/feedback`                          Record or correct
                                                               feedback

  GET                     `/users/{user_id}/feedback`          Retrieve feedback
                                                               history

  GET                     `/users/{user_id}/recommendations`   Retrieve top-K
                                                               recommendations

  POST                    `/users/{user_id}/retraining`        Request controlled
                                                               retraining

  GET                     `/models/current`                    Active model and
                                                               feature versions

  GET                     `/health/live`                       Process liveness

  GET                     `/health/ready`                      Readiness and artifact
                                                               checks

  GET                     `/metrics`                           Lightweight operational
                                                               metrics if enabled
  ------------------------------------------------------------------------------------

Do not expose unrestricted training endpoints publicly. In a local
portfolio demo, developer/admin operations can be protected or disabled
in public mode.

### 9.2 API requirements

-   Pydantic request and response schemas.
-   Validation of IDs, K values, actions, and filters.
-   Pagination and bounded result sizes.
-   Consistent error response format.
-   Timeouts for external dependencies.
-   Structured logs with request IDs.
-   No secrets or private user feedback in logs.
-   Model artifacts loaded once per process.
-   Explicit behavior when model artifacts are missing.
-   Readiness check validates required files and database connection.

### 9.3 Database entities

Suggested initial tables:

**users** - user_id - display_name or local alias - created_at

**lego_sets** - set_id - name - year - theme_id - num_parts -
image_path - image_status - source metadata

**feedback_events** - event_id - user_id - set_id - action -
created_at - impression_id, nullable

**current_feedback** - user_id - set_id - current_rating - updated_at

**recommendation_impressions** - impression_id - user_id - set_id -
rank - score - model_version - generated_at

**model_versions** - model_version - feature_version - dataset_version -
artifact_path - evaluation summary - status - created_at

Add indexes for set ID, user ID, feedback timestamp, and recommendation
lookup. Enforce foreign keys and user/set uniqueness where appropriate.

### 9.4 Streamlit pages

1.  **Discover:** catalog browsing and filters.
2.  **Swipe:** like, dislike, skip, undo.
3.  **For You:** top recommendations and explanations.
4.  **My Preferences:** feedback history and preference summary.
5.  **Model Lab:** baseline comparisons and learning curves.
6.  **System Info:** active model, dataset version, artifact status, and
    latency.

The UI must display missing-image fallbacks and useful empty states. Do
not show fake metrics or hard-coded recommendations in the finished
demo.

------------------------------------------------------------------------

## 10. MLOps, artifacts, and model promotion

### 10.1 Versioned artifacts

Every model run should be traceable to:

-   Source code version/commit.
-   Dataset version.
-   Feedback cutoff/snapshot.
-   Feature schema version.
-   CLIP checkpoint and preprocessing version.
-   Training configuration.
-   Random seed.
-   Evaluation protocol.
-   Metrics.
-   Model artifact checksum.

### 10.2 MLflow

Use MLflow to log:

-   Parameters.
-   Training data version.
-   Feature configuration.
-   Evaluation metrics.
-   Model artifacts where practical.
-   Run notes and tags.

Keep large image collections and bulky embeddings outside normal Git
history.

### 10.3 Promotion policy

A candidate model should be promoted only if:

-   Training completed successfully.
-   Artifact loads successfully.
-   Input/output schema matches.
-   Predictions are finite and within valid ranges.
-   Critical evaluation metrics meet pre-defined criteria.
-   It does not violate agreed regression thresholds.
-   The previous model remains available for rollback.

For a small dataset, avoid overly rigid thresholds that pretend metrics
are statistically certain. Document the sample size and uncertainty.

### 10.4 Reproducibility

Provide commands for: - Ingesting data. - Validating data. - Generating
embeddings. - Building the index. - Training a candidate model. -
Evaluating models. - Promoting a model. - Starting the API. - Starting
the UI.

All commands should work from a clean documented environment.

------------------------------------------------------------------------

## 11. Testing strategy

### 11.1 Unit tests

-   Catalog validation.
-   Image validation.
-   Feature preprocessing.
-   Embedding dimensions and normalization.
-   Set-ID/vector alignment.
-   FAISS index mapping.
-   Recommendation exclusions.
-   Ranking determinism.
-   Metric calculations.
-   Model serialization/loading.

### 11.2 Integration tests

-   Ingestion to processed catalog.
-   Image to embedding artifact.
-   Embedding artifact to index.
-   Feedback to profile.
-   Profile to recommendations.
-   Candidate training to evaluation.
-   API feedback submission to persisted database state.

### 11.3 API tests

-   Valid request.
-   Invalid set ID.
-   Invalid feedback action.
-   Unknown user.
-   Empty catalog.
-   Missing model artifact.
-   Out-of-range K.
-   Duplicate feedback.
-   Database unavailable.
-   User isolation.

### 11.4 Regression tests

Maintain a small fixed fixture dataset with known expected properties.
Do not require a model to produce one exact recommendation if numerical
or library changes make ranking ties possible; test invariants and
tolerances.

### 11.5 Quality gates

-   Ruff check passes.
-   Formatting passes.
-   Pytest suite passes.
-   No committed secrets.
-   Data/artifact paths are not accidentally committed.
-   Build and startup instructions are verified.
-   Evaluation report is generated from code.

------------------------------------------------------------------------

## 12. Monitoring and reliability

Monitor what is meaningful at this project's scale.

### System metrics

-   API request count.
-   Error count/rate.
-   Recommendation latency.
-   Database errors.
-   Artifact load failures.
-   Embedding job duration and failure count.

### ML metrics

-   Feedback counts by action.
-   Positive/negative distribution.
-   User feedback volume.
-   Candidate retrieval count.
-   Recommendation coverage.
-   Offline Precision@K and NDCG@K by model version.
-   Feature distribution changes.

### Drift caution

Feature distribution change is a signal to investigate, not proof that
recommendation quality has degraded. True performance monitoring
requires new labeled feedback or an appropriate evaluation set.

### Reliability behavior

-   Retry transient data-source errors.
-   Use bounded retries.
-   Preserve the previous working model on failed promotion.
-   Return a documented fallback when personalized artifacts are
    unavailable.
-   Never silently return fabricated recommendations.
-   Log enough context to debug without exposing sensitive data.

------------------------------------------------------------------------

## 13. Security and privacy

-   Keep `.env` out of Git.
-   Provide `.env.example` with placeholders only.
-   Validate all inputs.
-   Use parameterized database operations/ORM.
-   Apply user scoping to all feedback and recommendation queries.
-   Avoid collecting unnecessary personal data.
-   Do not expose training/admin endpoints without protection.
-   Do not log credentials or private feedback payloads.
-   Document data retention and deletion behavior.
-   Use HTTPS and appropriate authentication if deployed publicly.
-   Treat external image metadata and URLs as untrusted input.

For a local demo, a simple user profile selector may be acceptable, but
do not describe it as secure authentication.

------------------------------------------------------------------------

## 14. Deployment plan

### Stage 1 --- Local development

-   Windows-native Python environment.
-   SQLite database.
-   Local artifacts.
-   FastAPI backend.
-   Streamlit frontend.
-   CPU inference.
-   No paid services.

### Stage 2 --- Reproducible packaging

-   Dockerfile for backend.
-   Optional frontend container.
-   Compose file only when it simplifies startup.
-   Persistent volume for database and artifacts.
-   Health checks.
-   Environment-based configuration.

Docker is optional on the target laptop. The native local setup must
remain documented.

### Stage 3 --- Optional public demo

Only after local quality gates pass:

-   Select a hosting platform after checking current free-tier limits.
-   Use a small catalog or precomputed artifacts.
-   Do not assume a free tier provides persistent disk or enough RAM.
-   Protect user data and admin endpoints.
-   Document cold starts, sleep behavior, and storage limitations.
-   Provide a local demo path if public hosting is unavailable.

------------------------------------------------------------------------

## 15. Repository structure

Use a modular monolith and keep responsibilities clear.

``` text
BrickMatch-AI/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   ├── schemas/
│   │   └── dependencies.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   ├── data/
│   │   ├── ingestion/
│   │   ├── validation/
│   │   └── repositories/
│   ├── features/
│   │   ├── image_embeddings.py
│   │   ├── metadata.py
│   │   └── feature_builder.py
│   ├── recommendation/
│   │   ├── baselines.py
│   │   ├── retrieval.py
│   │   ├── ranking.py
│   │   ├── personalization.py
│   │   └── explanations.py
│   ├── training/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── promotion.py
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── migrations/
│   └── main.py
├── frontend/
│   ├── pages/
│   ├── components/
│   └── streamlit_app.py
├── configs/
│   ├── app.yaml
│   ├── data.yaml
│   ├── features.yaml
│   └── experiments.yaml
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   └── splits/
├── artifacts/
│   ├── embeddings/
│   ├── indexes/
│   └── models/
├── experiments/
│   ├── results/
│   └── reports/
├── scripts/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── api/
├── docs/
│   ├── architecture.md
│   ├── data_card.md
│   ├── model_card.md
│   ├── experiments.md
│   └── api.md
├── .github/
│   └── workflows/
│       └── ci.yml
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

Do not create empty abstractions for every folder on day one. Add
modules when the corresponding phase needs them.

------------------------------------------------------------------------

## 16. Phase-by-phase execution plan

Each phase has an objective, tasks, deliverables, tests, and a
completion gate. The coding agent must not silently skip a gate.

### Phase 0 --- Machine and repository preflight

**Tasks** - Confirm Windows version, Python availability, RAM, disk,
CPU, and GPU. - Create repository and virtual environment. - Verify
Python and package installation. - Test CPU PyTorch and one CLIP image
inference. - Test FAISS installation; verify fallback if unavailable. -
Decide local storage paths. - Create project README skeleton and
architecture decision record.

**Deliverables** - `docs/environment_report.md` - `pyproject.toml` or
pinned requirements. - Working environment. - Initial repository
structure.

**Gate** - One image successfully produces a finite CLIP embedding. - No
unsupported hardware assumptions remain.

### Phase 1 --- Dataset ingestion and validation

**Tasks** - Inspect actual Rebrickable files and terms. - Define
canonical catalog schema. - Implement repeatable ingestion. - Validate
IDs and metadata. - Build image manifest. - Download a small permitted
image sample. - Add retries, timeouts, and resume support. - Generate
data quality report.

**Deliverables** - Ingestion scripts. - Canonical processed catalog. -
Image manifest. - Data quality report. - Tests.

**Gate** - Re-running ingestion is safe. - Duplicate IDs are handled. -
Missing/broken images do not crash the pipeline. - Every accepted record
has a stable set ID.

### Phase 2 --- CLIP embedding and metadata pipeline

**Tasks** - Load selected CLIP checkpoint and processor. - Generate
embeddings in small CPU batches. - Save incrementally. - Normalize
vectors. - Persist ordered set-ID mapping. - Build metadata
preprocessing. - Version artifacts and configurations. - Add integrity
tests.

**Deliverables** - Embedding artifacts. - Metadata feature
transformer. - Feature manifest. - Runtime and memory benchmark.

**Gate** - Every embedding maps to the correct set. - Re-running
unchanged inputs does not needlessly recompute all vectors. - Pipeline
can recover from interruption.

### Phase 3 --- Retrieval and baselines

**Tasks** - Implement popularity/non-personalized baseline where source
data permits. - Implement visual nearest-neighbor retrieval. - Implement
metadata similarity. - Build FAISS index. - Implement fallback
nearest-neighbor backend. - Add candidate merging, deduplication, and
rated-item exclusions. - Benchmark candidate retrieval.

**Deliverables** - Three baseline strategies. - Index build/load
scripts. - Retrieval benchmark. - Tests.

**Gate** - Retrieval returns valid set IDs. - Similarity metric and
vector normalization are documented. - Candidate recall can be measured.

### Phase 4 --- Personalization and hybrid ranking

**Tasks** - Implement feedback event schema. - Implement per-user
preference profile. - Implement cold-start fallback. - Train Logistic
Regression when sufficient labels exist. - Compare visual-only,
metadata-only, and combined features. - Implement candidate scoring and
hybrid ranking. - Add diversity reranking as a separately evaluated
option. - Add evidence-based explanations.

**Deliverables** - Personalization service. - Model training script. -
Ranking service. - Model artifact format. - Tests.

**Gate** - Insufficient feedback uses a valid fallback. - A trained
model uses only eligible training data. - Already-rated items are
excluded. - Ranking is deterministic for the same inputs/model.

### Phase 5 --- Evaluation and experiments

**Tasks** - Define relevance and split protocol. - Create temporal
train/validation/test splits where possible. - Implement Precision@K,
Recall@K, NDCG@K, Hit Rate, coverage, diversity, and candidate recall. -
Compare all baselines. - Run feedback-size learning curve. - Measure CPU
embedding throughput and API latency. - Record experiment configurations
and results. - Write limitations.

**Deliverables** - Evaluation code. - Experiment result tables. -
Plots. - `docs/experiments.md` - Evaluation report.

**Gate** - No test leakage. - All reported values are generated by
code. - Sample sizes and limitations are stated. - The final test set
was not used for model selection.

### Phase 6 --- Database, API, and application

**Tasks** - Add SQLite schema and migrations. - Implement FastAPI
endpoints. - Add request/response schemas. - Implement user-scoped
feedback. - Implement recommendation endpoint. - Build Streamlit
discovery, swipe, recommendation, preference, and model pages. - Add
loading, empty, and error states. - Add impression logging if needed.

**Deliverables** - Working local application. - API documentation. -
Database schema. - Integration and API tests.

**Gate** - Feedback persists after restart. - User data is isolated. -
Recommendations change after eligible model updates. - UI does not
display fake model metrics.

### Phase 7 --- MLOps and reliability

**Tasks** - Integrate MLflow. - Add model and feature version
manifests. - Add candidate evaluation and promotion gate. - Implement
rollback to prior artifact. - Add structured logs and lightweight
metrics. - Add health/readiness checks. - Add failure handling and
fallback behavior.

**Deliverables** - Tracked experiments. - Versioned model artifacts. -
Promotion/rollback workflow. - Monitoring view.

**Gate** - Failed candidate promotion leaves the current model usable. -
Model can be loaded from a clean process. - Logs identify failures
without leaking private data.

### Phase 8 --- Testing, CI, packaging, and documentation

**Tasks** - Complete unit/integration/API tests. - Add Ruff and pytest
to GitHub Actions. - Add Docker packaging if feasible. - Verify clean
setup from README. - Write architecture, data, and model cards. - Record
demo walkthrough. - Review licenses and repository hygiene.

**Deliverables** - CI workflow. - Reproducible setup. - Final README. -
Demo video/GIF. - Model card and data card. - Release tag.

**Gate** - A second developer can follow the instructions. - Critical
tests pass. - No secrets or large raw datasets are committed. - Resume
claims match measured evidence.

------------------------------------------------------------------------

## 17. Definition of done

The project is ready for a resume when all critical items below are
true.

### ML

-   [ ] CLIP embeddings generated and versioned.
-   [ ] Metadata features implemented.
-   [ ] Popularity/non-personalized baseline implemented or limitation
    documented.
-   [ ] Visual retrieval baseline implemented.
-   [ ] Metadata baseline implemented.
-   [ ] Personalized classifier implemented with low-data fallback.
-   [ ] Hybrid ranking implemented.
-   [ ] Recommendation exclusions and diversity behavior tested.

### Evaluation

-   [ ] Train/validation/test methodology documented.
-   [ ] No leakage from test feedback.
-   [ ] Precision@K, Recall@K, NDCG@K implemented.
-   [ ] Candidate recall and coverage measured.
-   [ ] Baseline comparison completed.
-   [ ] Feedback-size learning curve completed.
-   [ ] Metrics are real, reproducible, and tied to sample sizes.

### Application

-   [ ] Swipe feedback works.
-   [ ] Feedback persists.
-   [ ] User isolation tested.
-   [ ] Recommendation API works.
-   [ ] UI has useful loading/error/empty states.
-   [ ] Explanations are based on actual features.

### Engineering

-   [ ] Reproducible ingestion and embedding jobs.
-   [ ] Tests pass.
-   [ ] CI runs tests.
-   [ ] Model artifacts are versioned.
-   [ ] Model promotion and rollback work.
-   [ ] Setup instructions verified from a clean environment.
-   [ ] No secrets committed.

### Portfolio

-   [ ] Architecture diagram.
-   [ ] Demo video or screenshots.
-   [ ] Evaluation report.
-   [ ] Data card and model card.
-   [ ] README with setup and reproduction commands.
-   [ ] Resume bullets backed by evidence.

------------------------------------------------------------------------

## 18. Resume and interview evidence

### Resume title

**BrickMatch AI --- Personalized Multimodal LEGO Recommendation Engine**

### Technology line

Python, PyTorch, CLIP, FAISS, Scikit-learn, FastAPI, Streamlit, MLflow,
SQLite, Docker

Only list technologies actually used in the completed project.

### Resume bullet templates

Fill the placeholders only after measuring them.

-   Built a multimodal recommendation pipeline combining pretrained CLIP
    image embeddings and structured catalog metadata across **\[N\] LEGO
    sets**.
-   Implemented visual candidate retrieval with **\[FAISS or verified
    fallback\]** and feedback-driven personalized ranking, comparing
    visual, metadata, and hybrid approaches.
-   Evaluated recommendation quality using **Precision@5, Recall@5, and
    NDCG@5**, achieving **\[measured result\]** against **\[named
    baseline\]** on **\[evaluation protocol/sample size\]**.
-   Automated reproducible feature generation, experiment tracking,
    model validation, and deployment checks using **\[tools actually
    implemented\]**.

### Interview stories to prepare

Be able to explain: - Why CLIP rather than a custom CNN? - Why use
embeddings instead of raw images in the recommender? - Why normalize
embeddings before cosine/inner-product retrieval? - Why FAISS, and what
is the fallback? - Why Logistic Regression? - What happens with only a
few ratings? - How do you avoid test leakage? - How do you handle cold
start? - How do you combine retrieval and ranking? - How do you know a
new model is better? - How do you roll back a bad model? - What are the
limits of a single-user dataset? - What did you measure on your own
laptop?

------------------------------------------------------------------------

## 19. Rules for GPT-6 / Astra / OpenCode implementation

Use the coding agent as a senior implementation partner, but keep
architectural ownership and verify every change.

### 19.1 Agent operating instructions

Give the coding agent these rules at the start of the project:

1.  Read this entire `BUILD_PLAN.md` before editing files.
2.  Inspect the existing repository and machine environment before
    proposing changes.
3.  Do not assume files, package versions, data fields, endpoints, or
    hardware that have not been verified.
4.  Use Windows-native commands and paths by default.
5.  Do not introduce WSL2, Kubernetes, Kafka, cloud services, or paid
    APIs without explicit approval.
6.  Keep the project CPU-first and compatible with approximately 8 GB
    RAM.
7.  Implement only the current phase and its approved dependencies.
8.  Before editing, explain the intended changes and list files to
    create or modify.
9.  Prefer small, maintainable modules over giant files.
10. Do not rewrite unrelated working code.
11. Add tests with every meaningful feature.
12. Run relevant tests and inspect their actual output.
13. Never claim a test passed unless it was executed and passed.
14. Never fabricate metrics, data, screenshots, deployment status, or
    completion.
15. Do not commit secrets, raw datasets, large images, or model weights.
16. Update `docs/` and the phase status after implementation.
17. If a decision is blocked by missing information, ask one focused
    question or propose a safe, documented default.
18. If a dependency fails on Windows, investigate the failure and use
    the documented fallback rather than silently changing the
    architecture.
19. Keep all model/data artifacts versioned and traceable.
20. Stop at the phase gate and report what remains before moving
    forward.

### 19.2 Required response format from the coding agent

For every task, the agent must return:

**Before implementation** - Understanding of the task. - Assumptions and
risks. - Architecture/implementation decision. - Files to create or
modify. - Exact acceptance criteria.

**After implementation** - Summary of changes. - Important design
decisions. - Commands executed. - Tests executed and actual results. -
Known limitations. - Manual checks for the developer. - Whether the
phase gate passed. - Recommended next task.

### 19.3 Prompt template for each phase

Copy this template and replace the bracketed fields.

``` text
Act as a senior ML engineer and Python software architect.

PROJECT:
BrickMatch AI — Personalized Multimodal LEGO Recommendation Engine.

SOURCE OF TRUTH:
Read BUILD_PLAN.md completely. Follow its architecture, constraints,
phase gates, testing requirements, and agent operating rules.

ENVIRONMENT:
Windows-native development.
Python 3.11.
Approximately 8 GB RAM.
CPU-first; no GPU requirement.
No paid APIs or services.
Do not introduce WSL2, Kubernetes, Kafka, or microservices.

CURRENT PHASE:
[PHASE NUMBER AND NAME]

TASK:
[ONE CLEAR IMPLEMENTATION TASK]

BEFORE CODING:
1. Inspect the repository and relevant existing files.
2. Explain your understanding and assumptions.
3. Identify files to create or modify.
4. Describe the implementation approach.
5. Identify resource, compatibility, and data-leakage risks.
6. Define testable acceptance criteria.

IMPLEMENTATION:
1. Implement only this task and its required dependencies.
2. Preserve working code and avoid unrelated refactoring.
3. Use typed, modular, maintainable Python.
4. Add tests for the new behavior.
5. Handle errors and invalid inputs.
6. Keep data and model artifacts out of Git.
7. Update documentation and configuration.
8. Do not invent source fields or fabricate data.

VERIFICATION:
1. Run the relevant tests.
2. Run lint/type checks that are configured.
3. Inspect actual command output.
4. Verify Windows compatibility.
5. Verify memory-conscious behavior.
6. Report any untested behavior honestly.

FINAL REPORT:
- Changes made.
- Files changed.
- Commands run.
- Actual test results.
- Known limitations.
- Manual verification steps.
- Phase-gate status.
- Next recommended task.

Do not start the next phase automatically.
Stop after this task and wait for review.
```

### 19.4 How to use GPT-6 / Astra effectively

-   Use a stronger reasoning mode for architecture, data leakage,
    experiment design, and debugging complex ML behavior.
-   Use a faster mode for small implementation tasks, documentation
    edits, and straightforward tests.
-   Give the agent one bounded task at a time.
-   Ask it to inspect files before editing.
-   Review diffs rather than accepting broad rewrites.
-   Run commands yourself when environment or dependency state is
    uncertain.
-   Keep this plan in the repository so future sessions can recover
    project context.

------------------------------------------------------------------------

## 20. Final project acceptance standard

The project is not complete just because the frontend looks polished.

It is complete when a reviewer can clone the repository, follow the
instructions, reproduce the feature pipeline, run the evaluation, start
the application, provide feedback, and observe the recommendation system
respond correctly.

The most valuable final evidence will be:

1.  A working application.
2.  A reproducible ML pipeline.
3.  A fair baseline comparison.
4.  Real evaluation results.
5.  Model and data versioning.
6.  Automated tests and CI.
7.  A clear demo and technical explanation.

**Build the smallest system that proves these capabilities, then improve
it based on measured weaknesses.**

That is the standard to target for a strong ML Engineer fresher
portfolio project.
