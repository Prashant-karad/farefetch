---
title: How to undo almost any Git mistake
publisher: code-dojo
price: 250
license: lic_read_24h
---
Committed to the wrong branch? Create the right branch, then reset the wrong one. Wrote a bad commit message? Use git commit --amend before you push. Deleted a branch by accident? git reflog lists every place your branch has pointed, so you can recover it. Pushed something you regret? Use git revert to add a new commit that undoes it, rather than rewriting shared history. The reflog is the safety net for almost everything.
