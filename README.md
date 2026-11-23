# Mauriegio Ventures Research Management System

RMS is a private, server-rendered workspace for tracing research records back to their sources and exact saved versions. The current release uses invented data. Paperclip manages the engineering work and founder decisions. Django and Django REST Framework serve the browser and API from the same permission-checked services. PostgreSQL stores the records and their history.

## Using the workspace

- **Home** shows the collections available to the signed-in user. Select a count to browse a collection or open the exact version of its latest addition. An unavailable count means the reader could not establish a total.
- **Sources and Ideas** capture citations, rights notes, proposed mechanisms, and each source version's contribution to an idea. Corrections retain their predecessors.
- **Search records** finds permitted metadata and record IDs across six collections. Select a collection or include earlier versions to locate a correction. Each result opens the exact saved version. Search terms travel in the form body.
- **Research cases** show their recorded owner, next action, and blocker on the overview and in the collection. The overview includes the latest case's revision time.
- **Research context and Hypotheses** connect an idea to a family, an investigation, and a manual prior-research assessment. A hypothesis retains its originating versions when those records change.
- **Test Plans** open from an exact hypothesis version. An editor can save an incomplete strategy specification, define a baseline and variations, record evaluation criteria and data requirements, and associate externally performed data checks. Historical definitions remain accessible.
- **Access** is enforced by the server. Editors can create and revise permitted records. Founder viewers can inspect them. The workspace details disclose the installed application commit.

The research record flow starts with a source, continues through an idea and hypothesis, and reaches a versioned test plan. Paperclip tracks new software delivery and independent acceptance. Real research intake, protected validation, broker connectivity, and trading require separate operating authority.

## Development and verification

The deployed stack uses Python 3.13, Django 5.2 LTS, Django REST Framework, PostgreSQL 17, HTML, CSS, and vanilla JavaScript. The repository has no frontend build step. Development and staging use separate configurations. Keep hostnames, credentials, database contents, and private evidence outside Git.

On the supported Linux development workspace, follow the [Python and PostgreSQL setup](docs/rms-python-environment.md). Use the project interpreter with the dependencies in `requirements.lock`. From the repository root, the following checks cover framework configuration, the permission-scoped home dashboard, template rendering, JavaScript editing behavior, and the staging recipe.

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py test tests.django_hypothesis_frontend_navigation_tests tests.django_hypothesis_frontend_shell_tests tests.django_test_plan_frontend_render_tests
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.js
```

Run the full Django regression suite against a disposable PostgreSQL 17 development cluster. The test login needs permission to create its own test databases. The two source and idea concurrency tests use separate, newly migrated databases so concurrent requests commit normally while history guards stay active.

```sh
.venv/bin/python manage.py test tests --pattern='django*tests.py' --noinput
```

Database-backed acceptance uses the designated test facility. Preserve historical records and existing users. See the [Hypothesis contract](docs/RMS_HYPOTHESIS_DESIGN_CONTRACT_V1_0.md), [Test Plan contract](docs/RMS_STRATEGY_SPECIFICATION_AND_TEST_PLAN_DESIGN_CONTRACT_V1_0.md), and [Test Plan API](docs/RMS-TP-API-1.md) for interfaces and scope.

## Building an application release

Use a clean checkout of the exact reviewed commit. Record the commit and tree independently from the reviewed branch or pull request, and provide both to the builder. Supply a new output directory outside the checkout.

```sh
python3 staging/build-release.py /absolute/path/to/new-package FULL_COMMIT_SHA FULL_TREE_SHA
```

The package contains the product archive, checksums, a per-file inventory, Dockerfile, runtime adapter, and Compose template. The builder checks the Git tree and the runtime verifies the extracted files and static assets. The historical increment builders remain available for their original manifests.

Operations deploys the application on the existing private VPS using its current Compose project, route, secret mounts, and PostgreSQL volume. Before applying a release, retain the previous app image and Compose configuration, inventory the database migration plan, and verify a local backup if the schema changes. Apply approved additive migrations once, update the application service, then compare its installed commit and tree against the reviewed package. Verify database health, the private authentication challenge, an authorized read, and the static assets. Roll back the application using the retained image and Compose configuration after checking schema compatibility. Never substitute the sample development settings for the installed private configuration.

The [staging README](staging/README.md) documents the original private-host contract. Release receipts in [docs/verification](docs/verification) describe the specific candidates and environments in which the checks ran.
