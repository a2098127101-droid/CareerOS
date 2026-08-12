# StepIn Windows Install

## Current fast path

1. Extract the reviewed StepIn release ZIP outside OneDrive-synced folders when possible.
2. Double-click `OPEN_StepIn.cmd`.
3. Allow the local environment to initialize or repair on first run.
4. Complete the Foundation and Learner Agent smoke flow before using the installation for a pilot.

The historical `OPEN_CareerOS.cmd` launcher and `CareerOS_H5_Showcase.html` fallback remain only for compatibility with existing shortcuts and older local packages. New documentation and release instructions use StepIn naming.

## Release boundary

Windows x64 remains a separate release gate. A reviewed build should be verified on real Windows hardware for fresh install, first launch, offline behavior where promised, save/restart persistence, export, backup, upgrade, migration, restore and uninstall/reinstall. Linux GitHub Actions do not substitute for this certification.
