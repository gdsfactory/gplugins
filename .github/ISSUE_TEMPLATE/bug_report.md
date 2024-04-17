---
name: Bug report
about: Create a report to help us improve
title: ''
labels: 'bug'
assignees: ''

---

**Describe the bug**
What's the bug?

**To Reproduce**
What's the code to reproduce the behavior? What commands or code did you write to get the error?
You can add screenshots to help explain your problem.
Make sure you include the all code for others to reproduce your issue.

**Expected behavior**
What would you like to happen?

**Suggested fix**
How could we fix the bug?

**Versions**
What version of gplugins and each gplugin are you using? Notice that we only may be able help you if you are using the latest version.
You can find the version by running:

```python
from gdsfactory.config import print_version_plugins

print_version_plugins()
```

And update to the latest version of all plugins by running:

```bash
pip install "gdsfactory[full]" --upgrade
```

Or only the specific plugin you are reporting:

```bash
pip install "gplugins[tidy3d]" --upgrade
```

Then copy paste the table so that we know which version of python and plugins you are using.
