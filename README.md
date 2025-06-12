# Jira to Bitrix24 Migration Tool

This Python-based utility migrates users, issues, and comments from a local Jira instance to a Bitrix24 portal via webhook API.
There are a lot of tools for migration from cloud Jira, but this one is simple and easy to use.

---

## Table of Contents

1. [Features](#features)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Usage](#usage)

   * [Migrating Users](#migrating-users)
   * [Migrating Issues](#migrating-issues)
6. [Command Line Options](#command-line-options)
7. [Logging](#logging)
8. [Error Handling](#error-handling)
9. [License](#license)

---

## Features

* Bulk migration of Jira users to Bitrix24 users
* Automated creation of Bitrix24 tasks from Jira issues
* Optional deletion and recreation of existing tasks
* Migration of issue comments as Bitrix24 task comments
* Retry logic and robust error handling for API calls

## Prerequisites

* Python 3.8 or newer
* `pip` package manager
* Access to Jira REST API with appropriate permissions
* Bitrix24 incoming webhook URL with rights to create users, tasks, and comments

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/TimurTsedik/jira_to_bitrix_migration_tool.git
   cd jira-to-bitrix-migrator
   ```
2. **Create and activate a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Create a `.env` file in the project root with the following variables:

```dotenv
# Jira connection settings
JIRA_URL=https://jira.your-domain.com
JIRA_USER=your-jira-username
JIRA_TOKEN=your-jira-api-token
MAX_RESULTS=50

# Bitrix24 incoming webhook URL (must end with '/')
BITRIX_WEBHOOK=https://your-domain.bitrix24.ru/rest/1/your-webhook-token/
```

* `MAX_RESULTS` controls the page size when fetching from Jira.

## Usage

Ensure your virtual environment is active and run the migration script:

```bash
python migrate.py [OPTIONS]
```

By default, the script will:

1. Migrate all active Jira users (A–Z prefix scan) to Bitrix24.
2. Create a placeholder **Nobody** user for unassigned issues.
3. Migrate issues from all Jira projects.
4. Create Bitrix24 tasks (optionally deleting existing by title).
5. Migrate comments into Bitrix24 task comments.

### Migrating Users

To run only the user migration step:

```bash
python migrate.py --step users
```

### Migrating Issues

To run only the issue and comment migration step (after users are mapped):

```bash
python migrate.py --step issues --project TTS --group 12
```

* `--project` restricts to a single Jira project key.
* `--group` sets the Bitrix24 workgroup ID for created tasks.

## Command Line Options

| Option          | Description                                    | Default |
| --------------- |------------------------------------------------| ------- |
| `--step`        | Which step to run: `users`, `issues`, or `all` | `all`   |
| `--project`     | Jira project key to migrate (issues only)      | *none*  |
| `--group`       | Bitrix24 workgroup ID for new tasks            | *none*  |

Use:

```bash
python migrate.py --help
```

for more details.

## Logging

All operations are logged to both the console and `migration.log` in the project root.

* **INFO**: high-level progress and summary
* **WARNING**: retries and recoverable issues
* **ERROR**: failures that may require manual intervention

## Error Handling

* Network errors and 5xx responses are retried automatically.
* Bitrix24 API errors (payload with `error` key) raise `BitrixAPIError` and are logged.
* Jira API errors raise `JiraAPIError` and are logged.
* Individual issue/comment failures do not stop the entire migration; errors are caught and logged.


## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

*Happy migrating!*
