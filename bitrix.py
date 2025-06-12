# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Timur Tsedik


import logging
from functools import lru_cache

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BitrixAPIError(Exception):
    pass

class BitrixFillInData:
    def __init__(self, in_bitrixWebHook: str):
        self.bitrixWebHook = in_bitrixWebHook
        self.session = Session()
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def callBitrixMethod(self, in_method: str, in_params: dict | list) -> dict:
        """General helper to call Bitrix24 via webhook with retry logic."""
        url = f"{self.bitrixWebHook}{in_method}"
        resp = self.session.post(url, json=in_params)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            msg = data.get("error_description", data["error"])
            raise BitrixAPIError(f"{in_method}: {msg!r}")
        return data.get("result", {})

    @lru_cache(maxsize=100)
    def findBitrixUserByEmail(self, in_email: str) -> int | None:
        """Return existing Bitrix24 user ID by email, or None."""
        params = {'filter': {'EMAIL': in_email}, 'start': 0}
        result = self.callBitrixMethod('user.get', params)
        if isinstance(result, list) and result:
            try:
                return int(result[0]['ID'])
            except (KeyError, ValueError):
                return None
        return None

    def addBitrixUser(self, in_user: dict, in_departmentNr: int = 1) -> dict:
        """Add a user to Bitrix24 portal based on Jira user."""
        # Разбираем displayName на имя и фамилию
        parts = in_user['displayName'].split()
        name = parts[0]
        lastName = parts[1] if len(parts) > 1 else ''

        # Структура полей согласно методу user.add
        fields = {
            'EMAIL': in_user['email'],
            'NAME': name,
            'LAST_NAME': lastName,
            "UF_DEPARTMENT": [in_departmentNr]
        }
        # Передаём поля напрямую без обёртки 'fields'
        result = self.callBitrixMethod('user.add', fields)
        logging.info(f"Created Bitrix24 user {result} for Jira user {in_user['key']}")
        return result

    def findBitrixTaskByTitle(self, in_title: str) -> int | None:
        """Return existing Bitrix24 task ID by exact title, or None."""
        params = {'filter': {'TITLE': in_title}, 'select': ['ID'], 'start': 0}
        result = self.callBitrixMethod('tasks.task.list', params)
        tasks = result.get('tasks', []) if isinstance(result, dict) else []
        if tasks:
            try:
                return int(tasks[0].get('ID') or tasks[0].get('id'))
            except (KeyError, ValueError):
                return None
        return None

    def deleteBitrixTask(self, id_taskId: int) -> bool:
        """Delete a task in Bitrix24 via tasks.task.delete."""
        result = self.callBitrixMethod('tasks.task.delete', {'taskId': id_taskId})
        if result:
            logging.info(f"Deleted Bitrix24 task {id_taskId}")
            return True
        else:
            logging.error(f"Failed to delete Bitrix24 task {id_taskId}")
            return False

    def createBitrixTask(self, in_issue: dict, in_contactMap: dict,
                         in_deleteIfExist: bool = False, in_taskGroup: int = None) -> dict | int:
        """Create a task in Bitrix24 based on a Jira issue, skipping if exists."""
        title = f"{in_issue['key']}: {in_issue['fields']['summary']}"
        existing = self.findBitrixTaskByTitle(title)

        if existing and not in_deleteIfExist:
            logging.info(f"Task '{title}' already exists as ID {existing}, skipping creation")
            return existing
        elif existing and in_deleteIfExist:
            self.deleteBitrixTask(existing)
        if in_issue['fields'].get('assignee', {}) is None:
            assignee = "Nobody"
        else:
            assignee = in_issue['fields'].get('assignee', {}).get('name')
        if in_issue['fields'].get('reporter', {}) is None:
            reporter = "Nobody"
        else:
            reporter = in_issue['fields'].get('reporter', {}).get('name')
        fields = {
            'TITLE': f"{in_issue['key']}: {in_issue['fields']['summary']}",
            'DESCRIPTION': in_issue['fields'].get('description', ''),
            'RESPONSIBLE_ID': in_contactMap.get(assignee),
            'CREATED_BY': in_contactMap.get(reporter),
            'CREATED_DATE': in_issue['fields'].get('created', ''),
            'CHANGED_DATE': in_issue['fields'].get('updated', ''),
            'GROUP_ID': in_taskGroup
        }
        result = self.callBitrixMethod('tasks.task.add', {'fields': fields})
        logging.info(f"Created Bitrix24 task {result} for Jira issue {in_issue['key']}")
        return result

    def getBitrixWorkgroups(self, in_filter: dict = None, in_select: list = None) -> list:
        """Fetch workgroups from Bitrix24 via socialnetwork.api.workgroup.list."""
        params = {}
        if in_filter is not None:
            params['filter'] = in_filter
        if in_select is not None:
            params['select'] = in_select
        result = self.callBitrixMethod('socialnetwork.api.workgroup.list', params)
        return result.get('workgroups', [])

if __name__ == "__main__":
    pass