import os
import logging

from dotenv import load_dotenv
from requests import Session
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class JiraAPIError(Exception):
    pass

class JiraFetchData:
    def __init__(self, in_jiraUrl: str, in_jiraUserName: str, in_jiraPass: str, in_maxResults: int = 50, in_verifySsl: bool = False):
        self.jiraUrl = in_jiraUrl
        self.maxResults = in_maxResults
        self.verify = in_verifySsl
        self.auth = HTTPBasicAuth(in_jiraUserName, in_jiraPass)

        self.session = Session()
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get(self, in_path: str, **kwargs) -> list | dict:
        url = f"{self.jiraUrl}{in_path}"
        resp = self.session.get(url, auth=self.auth, verify=self.verify, **kwargs)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            msg = data.get("error_description", data["error"])
            raise JiraAPIError(f"{in_path}: {msg!r}")
        return data

    def fetchJiraUsers(self, in_prefix: str) -> list:
        """Fetch all Jira users whose username starts with the given prefix."""
        users = []
        startAt = 0
    
        while True:
            params = {'username': in_prefix, 'startAt': startAt, 'maxResults': self.maxResults}
            resp = self._get("/rest/api/2/user/search", params=params)
            if not isinstance(resp, list) or not resp:
                break
            for u in resp:
                users.append({
                    'key': u.get('name'),
                    'email': u.get('emailAddress'),
                    'displayName': u.get('displayName'),
                    'active': u.get('active')
                })
            if len(resp) < self.maxResults:
                break
            startAt += len(resp)
    
        logging.info(f"Fetched {len(users)} Jira users with prefix '{in_prefix}'")
        return users
    
    def collectAssigneeKeys(self) -> list:
        """Collect all distinct assignee usernames across all Jira issues."""
        keys = set()
        usersData = []
        for proj in self.fetchJiraProjects():
            for issue in self.fetchJiraIssues(proj['key']):
                assignee = issue['fields'].get('assignee')
                if assignee and assignee.get('name'):
                    keyLen = len(keys)
                    keys.add(assignee['name']) # assignee['emailAddress'],
                    if len(keys) > keyLen:
                        usersData.append([assignee['emailAddress'], assignee['name']])
        logging.info(f"Collected {len(keys)} distinct assignee usernames from Jira issues")
        return usersData
    
    def fetchJiraUserByKey(self, in_username: str) -> dict | None:
        """Fetch a single Jira user by exact username."""
        params = {'username': in_username, 'maxResults': 1}
        resp = self._get("/rest/api/2/user/search", params=params)
        for u in resp:
            if u.get('name') == in_username:
                return {
                    'key': u.get('name'),
                    'email': u.get('emailAddress'),
                    'displayName': u.get('displayName'),
                    'active': u.get('active', False)
                }
        return None
    
    def fetchJiraProjects(self) -> list:
        """Fetch all Jira projects in one go."""
        ret = self._get("/rest/api/2/project")
        logging.info(f"Fetched {len(ret)} Jira projects")
        return ret

    def fetchJiraIssues(self, in_projectKey: str) -> list:
        """Fetch all issues for a given Jira project."""
        issues = []
        startAt = 0
        jql = f"project={in_projectKey} ORDER BY created ASC"
    
        while True:
            params = {
                'jql': jql,
                'startAt': startAt,
                'maxResults': self.maxResults,
                'fields': 'summary,description,issuetype,assignee,reporter,created,updated'
            }
            resp = self._get("/rest/api/2/search", params=params)
            batch = resp.get('issues', [])
            if not batch:
                break
            issues.extend(batch)
            if len(batch) < self.maxResults:
                break
            startAt += len(batch)
    
        logging.info(f"Fetched {len(issues)} issues from project {in_projectKey}")
        return issues
    
    def fetchComments(self, in_issueKey: str) -> list:
        """Fetch comments for a given Jira issue."""
        resp = self._get(f"/rest/api/2/issue/{in_issueKey}/comment")
        comments = resp.get('comments', [])
        logging.info(f"Fetched {len(comments)} comments for issue {in_issueKey}")
        return comments


if __name__ == "__main__":
    pass