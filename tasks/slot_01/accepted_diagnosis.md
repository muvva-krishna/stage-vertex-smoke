# Accepted diagnosis rubric (human scoring reference)

Root cause: after the converted version 2 file was written but before the progress sidecar was marked complete, restart handling re-runs the version 1 conversion on a version 2 object. The converter reads legacy preference keys and overwrites the version 2 `extensions` field with an empty object. A correct repair must recognize a complete version 2 target as already committed and mark it complete without re-normalizing user data. It must also recover a malformed in-progress target from the saved version 1 backup when available.

Give full diagnosis credit for identifying both the restart/re-conversion path and the loss of version 2 extension fields. Give partial credit for identifying that restart handling drops preferences without explaining why. A patch that restores the version 1 backup and re-runs conversion is also acceptable if it passes every behavioral oracle group.
