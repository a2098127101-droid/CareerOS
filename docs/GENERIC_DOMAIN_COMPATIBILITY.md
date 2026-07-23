# Generic domain compatibility

CareerOS Core now exposes canonical role semantics:

- `platform_admin`
- `organization_admin`
- `advisor`
- `participant`

Legacy storage/API role IDs remain accepted:

- `super_admin`
- `school_admin`
- `teacher`
- `student`

During the compatibility period, canonical roles are mapped to legacy storage IDs to avoid destructive data migrations.

Generic route aliases are available:

- `/participant` → existing participant/user workspace
- `/advisor` → existing advisor workspace
- `/api/admin/groups` → legacy class/group storage
- `/api/advisor/dashboard` → legacy teacher/advisor operations API

The canonical `ParticipantProfile` provides a cross-industry view over the legacy profile without deleting historical fields. Vertical-specific attributes should move toward `custom_attributes` in later migrations.

Product presets now include:

- `career_development`
- `campus_career`
- `career_service`
- `career_competition`
- `enterprise_talent`
