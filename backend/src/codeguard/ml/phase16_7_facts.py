"""Phase 16.7 inventory-only facts curated from official Python documentation.

These records are not candidate-generation inputs. Each locator and evidence
summary was checked against the linked official documentation page; independent
review remains pending.
"""
from __future__ import annotations

from datetime import date

LICENSE = "Python Software Foundation License Version 2; retain attribution and source URL"
LICENSE_URL = "https://docs.python.org/3/license.html"
REVIEW_STATUS = "pending_independent_review"

# key, topic, URL, title, section, locator, evidence summary, canonical fact
_ROWS = [
    ("execmodel_class_scope_methods", "scope and namespaces", "https://docs.python.org/3/reference/executionmodel.html", "Execution model", "Resolution of names", "§4.2 Resolution of names; class blocks", "Names defined in a class block do not extend to method code blocks.", "Names defined in a class body are not directly in scope inside its methods."),
    ("execmodel_comprehension_class_scope", "comprehensions and scope", "https://docs.python.org/3/reference/executionmodel.html", "Execution model", "Resolution of names", "§4.2 Resolution of names; class blocks", "The class-scope limitation includes comprehensions and generator expressions.", "A comprehension or generator expression in a class body does not directly resolve names from that class namespace."),
    ("execmodel_free_names_runtime", "scope and namespaces", "https://docs.python.org/3/reference/executionmodel.html", "Execution model", "Interaction with dynamic features", "§4.2.6 Interaction with dynamic features", "Resolution of free variables occurs at runtime, not compile time.", "Python resolves free-variable names at runtime rather than compile time."),
    ("execmodel_unhandled_traceback", "exceptions", "https://docs.python.org/3/reference/executionmodel.html", "Execution model", "Exceptions", "§4.3 Exceptions", "An unhandled exception terminates program execution or returns to the interactive loop and prints a traceback, except SystemExit.", "An unhandled exception normally prints a traceback when execution terminates, except for SystemExit."),
    ("execmodel_exception_message_api", "exceptions", "https://docs.python.org/3/reference/executionmodel.html", "Execution model", "Exceptions", "§4.3 Exceptions", "Exception message contents may change between interpreter versions without warning and are not part of the Python API.", "Programs intended to run across Python versions should not rely on exception message text as a stable API."),
    ("execmodel_finally_cleanup", "exceptions and control flow", "https://docs.python.org/3/reference/executionmodel.html", "Execution model", "Exceptions", "§4.3 Exceptions", "A finally clause executes whether or not an exception occurred in the preceding try block.", "A try statement's finally clause runs whether or not the preceding code raised an exception."),
    ("threading_lock_any_release", "threading", "https://docs.python.org/3/library/threading.html", "Thread-based parallelism", "Lock objects", "Lock objects — release()", "A primitive Lock can be released by any thread, not only the thread that acquired it.", "A Python threading.Lock may be released by a thread other than the acquiring thread."),
    ("threading_lock_unlocked_release", "threading and exceptions", "https://docs.python.org/3/library/threading.html", "Thread-based parallelism", "Lock objects", "Lock objects — release()", "Calling release on an unlocked Lock raises RuntimeError.", "Calling release() on an already unlocked threading.Lock raises RuntimeError."),
    ("threading_rlock_owner", "threading", "https://docs.python.org/3/library/threading.html", "Thread-based parallelism", "RLock objects", "RLock objects", "An RLock must be released by the thread that acquired it.", "A threading.RLock must be released by its owning thread."),
    ("threading_rlock_recursion", "threading", "https://docs.python.org/3/library/threading.html", "Thread-based parallelism", "RLock objects", "RLock objects", "The acquiring thread may acquire an RLock repeatedly without blocking and must release it once per acquisition.", "A thread that acquires an RLock multiple times must release it the same number of times."),
    ("threading_condition_wait_lock", "threading", "https://docs.python.org/3/library/threading.html", "Thread-based parallelism", "Condition objects", "Condition objects — wait()", "Condition.wait releases its underlying lock while blocked and reacquires it before returning.", "Condition.wait() releases the associated lock while waiting and reacquires it before it returns."),
    ("threading_condition_wait_requires_lock", "threading and exceptions", "https://docs.python.org/3/library/threading.html", "Thread-based parallelism", "Condition objects", "Condition objects — wait()", "Calling Condition.wait without having acquired its lock raises RuntimeError.", "Condition.wait() raises RuntimeError if called by a thread that does not hold the condition's lock."),
    ("warnings_default_repeat_location", "warnings", "https://docs.python.org/3/library/warnings.html", "Warning control", "Repeated Warning Suppression Criteria", "Repeated Warning Suppression Criteria — default", "Under the default action, repeat identity includes message, category, module, and line number.", "The default warnings action treats occurrences as repeats only when message, category, module, and line number all match."),
    ("warnings_once_repeat_category", "warnings", "https://docs.python.org/3/library/warnings.html", "Warning control", "Repeated Warning Suppression Criteria", "Repeated Warning Suppression Criteria — once", "Under once, repeat identity uses message and category while ignoring module and line number.", "The once warnings action ignores module and line number when deciding whether a warning repeats."),
    ("warnings_later_filters_precedence", "warnings", "https://docs.python.org/3/library/warnings.html", "Warning control", "Describing Warning Filters", "Describing Warning Filters", "For multiple filters on one PYTHONWARNINGS line, later filters take precedence.", "Later comma-separated filters in PYTHONWARNINGS take precedence over earlier filters."),
    ("warnings_catch_restores_filter", "warnings and context managers", "https://docs.python.org/3/library/warnings.html", "Warning control", "Testing Warnings", "Testing Warnings; catch_warnings", "On context-manager exit, catch_warnings restores the filter and showwarning function; the guarantee applies in a single-threaded application.", "warnings.catch_warnings restores the warning filter on exit in the documented single-threaded case."),
    ("os_environ_import_snapshot", "os and environment", "https://docs.python.org/3/library/os.html", "Miscellaneous operating system interfaces", "Process Parameters", "os.environ", "os.environ is captured when os is first imported; later external environment changes are not reflected unless the mapping itself is modified.", "Changes made outside os.environ after the os module is imported are not reflected in the captured os.environ mapping."),
    ("os_environ_putenv_sync", "os and environment", "https://docs.python.org/3/library/os.html", "Miscellaneous operating system interfaces", "Process Parameters", "os.environ", "Modifying os.environ calls putenv automatically; calling putenv directly does not change os.environ.", "Updating os.environ invokes putenv, but calling putenv directly does not update the os.environ mapping."),
    ("os_windows_env_uppercase", "os and environment", "https://docs.python.org/3/library/os.html", "Miscellaneous operating system interfaces", "Process Parameters", "os.environ", "On Windows, os.environ keys are converted to uppercase for getting, setting, and deleting.", "On Windows, os.environ normalizes environment-variable keys to uppercase when accessing or modifying them."),
]

def facts() -> list[dict[str, str]]:
    """Return complete, stable-key inventory rows without candidate claims."""
    today = date.today().isoformat()
    result = []
    for key, topic, url, title, section, locator, evidence, canonical in _ROWS:
        group = f"page:{url}"
        result.append({
            "fact_id": key, "fact_key": key, "canonical_fact": canonical,
            "fact_statement": canonical, "topic": topic, "source_url": url,
            "source_title": title, "section": section,
            "evidence_locator": locator, "evidence_text": evidence,
            "license": LICENSE, "license_url": LICENSE_URL,
            "evidence_group": group, "source_group": group,
            "claim_family": key, "source_type": "official_python_documentation",
            "retrieval_date": today,
            "provenance_status": "Official Python documentation page checked; evidence paraphrased; independent review pending",
            "review_priority": "inventory_only_pending_review",
            "fact_review_status": REVIEW_STATUS,
        })
    return result
