-- CareerOS v1.5 Domain Intelligence PostgreSQL baseline generated from schema_manifest.json


CREATE TABLE ai_tasks (
	task_id TEXT, 
	session_id TEXT DEFAULT '' NOT NULL, 
	tenant_id TEXT NOT NULL, 
	owner_user_id TEXT DEFAULT '' NOT NULL, 
	title TEXT NOT NULL, 
	task_type TEXT NOT NULL, 
	status TEXT DEFAULT 'todo' NOT NULL, 
	priority TEXT DEFAULT 'normal' NOT NULL, 
	source TEXT DEFAULT 'system' NOT NULL, 
	payload_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	version INTEGER DEFAULT 1 NOT NULL, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_ai_tasks PRIMARY KEY (task_id)
);


CREATE TABLE analytics_events (
	event_id SERIAL, 
	tenant_id TEXT NOT NULL, 
	user_id TEXT DEFAULT '' NOT NULL, 
	session_id TEXT DEFAULT '' NOT NULL, 
	event_name TEXT NOT NULL, 
	properties_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_analytics_events PRIMARY KEY (event_id)
);


CREATE TABLE artifact_series (
	artifact_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	owner_user_id TEXT DEFAULT '' NOT NULL, 
	kind TEXT NOT NULL, 
	title TEXT NOT NULL, 
	current_version_id TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	version INTEGER DEFAULT 1 NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_artifact_series PRIMARY KEY (artifact_id)
);


CREATE TABLE artifact_template_definitions (
	template_id TEXT, 
	tenant_id TEXT NOT NULL, 
	kind TEXT NOT NULL, 
	label TEXT NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	status TEXT DEFAULT 'draft' NOT NULL, 
	aliases_json TEXT DEFAULT '[]' NOT NULL, 
	schema_json TEXT DEFAULT '{}' NOT NULL, 
	renderer TEXT DEFAULT 'structured_text' NOT NULL, 
	review_rubric TEXT DEFAULT 'general_v1' NOT NULL, 
	presets_json TEXT DEFAULT '[]' NOT NULL, 
	created_by TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_artifact_template_definitions PRIMARY KEY (template_id)
);


CREATE TABLE billing_events (
	event_id TEXT, 
	provider TEXT NOT NULL, 
	event_key TEXT NOT NULL, 
	event_type TEXT DEFAULT '' NOT NULL, 
	tenant_id TEXT DEFAULT '' NOT NULL, 
	payload_hash TEXT DEFAULT '' NOT NULL, 
	status TEXT DEFAULT 'received' NOT NULL, 
	result_json TEXT DEFAULT '{}' NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_billing_events PRIMARY KEY (event_id), 
	CONSTRAINT uq_billing_events_1 UNIQUE (provider, event_key)
);


CREATE TABLE billing_orders (
	order_id TEXT, 
	tenant_id TEXT NOT NULL, 
	plan_id TEXT NOT NULL, 
	provider TEXT DEFAULT 'mock' NOT NULL, 
	external_order_id TEXT DEFAULT '' NOT NULL, 
	status TEXT DEFAULT 'pending' NOT NULL, 
	amount_minor INTEGER DEFAULT 0 NOT NULL, 
	currency TEXT DEFAULT 'CNY' NOT NULL, 
	metadata_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_billing_orders PRIMARY KEY (order_id)
);


CREATE TABLE capabilities (
	capability_id TEXT, 
	tenant_id TEXT NOT NULL, 
	taxonomy_id TEXT NOT NULL, 
	capability_key TEXT NOT NULL, 
	name TEXT NOT NULL, 
	category TEXT DEFAULT 'general' NOT NULL, 
	description TEXT DEFAULT '' NOT NULL, 
	aliases_json TEXT DEFAULT '[]' NOT NULL, 
	level_scale_json TEXT DEFAULT '{}' NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	created_by TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_capabilities PRIMARY KEY (capability_id), 
	CONSTRAINT uq_capabilities_1 UNIQUE (tenant_id, taxonomy_id, capability_key)
);


CREATE TABLE capability_assessment_evidence (
	link_id TEXT, 
	tenant_id TEXT NOT NULL, 
	assessment_id TEXT NOT NULL, 
	capability_id TEXT NOT NULL, 
	claim_id TEXT DEFAULT '' NOT NULL, 
	evidence_id TEXT DEFAULT '' NOT NULL, 
	contribution_type TEXT NOT NULL, 
	potential_weight FLOAT DEFAULT 0 NOT NULL, 
	verified_weight FLOAT DEFAULT 0 NOT NULL, 
	explanation TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_capability_assessment_evidence PRIMARY KEY (link_id)
);


CREATE TABLE capability_assessments (
	assessment_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	owner_user_id TEXT NOT NULL, 
	capability_id TEXT NOT NULL, 
	assessment_version INTEGER NOT NULL, 
	potential_score FLOAT DEFAULT 0 NOT NULL, 
	verified_score FLOAT DEFAULT 0 NOT NULL, 
	confidence FLOAT DEFAULT 0 NOT NULL, 
	methodology_version TEXT NOT NULL, 
	explanation_json TEXT DEFAULT '{}' NOT NULL, 
	created_by TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_capability_assessments PRIMARY KEY (assessment_id), 
	CONSTRAINT uq_capability_assessments_1 UNIQUE (tenant_id, session_id, capability_id, assessment_version)
);


CREATE TABLE capability_taxonomies (
	taxonomy_id TEXT, 
	tenant_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	description TEXT DEFAULT '' NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	created_by TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_capability_taxonomies PRIMARY KEY (taxonomy_id), 
	CONSTRAINT uq_capability_taxonomies_1 UNIQUE (tenant_id, name)
);


CREATE TABLE capability_versions (
	capability_version_id TEXT, 
	tenant_id TEXT NOT NULL, 
	capability_id TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	snapshot_json TEXT NOT NULL, 
	changed_by TEXT DEFAULT '' NOT NULL, 
	change_reason TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_capability_versions PRIMARY KEY (capability_version_id), 
	CONSTRAINT uq_capability_versions_1 UNIQUE (capability_id, version)
);


CREATE TABLE career_gap_versions (
	gap_version_id TEXT, 
	tenant_id TEXT NOT NULL, 
	gap_id TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	snapshot_json TEXT NOT NULL, 
	changed_by TEXT DEFAULT '' NOT NULL, 
	change_reason TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_career_gap_versions PRIMARY KEY (gap_version_id), 
	CONSTRAINT uq_career_gap_versions_1 UNIQUE (gap_id, version)
);


CREATE TABLE career_gaps (
	gap_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	owner_user_id TEXT NOT NULL, 
	job_id TEXT NOT NULL, 
	requirement_id TEXT NOT NULL, 
	capability_id TEXT DEFAULT '' NOT NULL, 
	gap_type TEXT NOT NULL, 
	severity FLOAT DEFAULT 0 NOT NULL, 
	status TEXT DEFAULT 'open' NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	potential_score FLOAT DEFAULT 0 NOT NULL, 
	verified_score FLOAT DEFAULT 0 NOT NULL, 
	required_score FLOAT DEFAULT 60 NOT NULL, 
	explanation_json TEXT DEFAULT '{}' NOT NULL, 
	created_by TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_career_gaps PRIMARY KEY (gap_id), 
	CONSTRAINT uq_career_gaps_1 UNIQUE (tenant_id, session_id, job_id, requirement_id, capability_id)
);


CREATE TABLE claim_capability_links (
	link_id TEXT, 
	tenant_id TEXT NOT NULL, 
	claim_id TEXT NOT NULL, 
	capability_id TEXT NOT NULL, 
	relation TEXT DEFAULT 'indicates' NOT NULL, 
	confidence FLOAT DEFAULT 0 NOT NULL, 
	explanation TEXT DEFAULT '' NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_claim_capability_links PRIMARY KEY (link_id), 
	CONSTRAINT uq_claim_capability_links_1 UNIQUE (tenant_id, claim_id, capability_id, relation)
);


CREATE TABLE claim_evidence_links (
	link_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	claim_id TEXT NOT NULL, 
	evidence_id TEXT NOT NULL, 
	relation TEXT DEFAULT 'candidate_support' NOT NULL, 
	confidence FLOAT DEFAULT 0 NOT NULL, 
	verification_status TEXT DEFAULT 'UNVERIFIED' NOT NULL, 
	explanation TEXT DEFAULT '' NOT NULL, 
	verifier_type TEXT DEFAULT 'deterministic' NOT NULL, 
	verified_by TEXT DEFAULT '' NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_claim_evidence_links PRIMARY KEY (link_id), 
	CONSTRAINT uq_claim_evidence_links_1 UNIQUE (tenant_id, claim_id, evidence_id, relation)
);


CREATE TABLE data_subject_requests (
	request_id TEXT, 
	tenant_id TEXT NOT NULL, 
	user_id TEXT NOT NULL, 
	request_type TEXT NOT NULL, 
	status TEXT DEFAULT 'pending' NOT NULL, 
	notes TEXT DEFAULT '' NOT NULL, 
	result_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_data_subject_requests PRIMARY KEY (request_id)
);


CREATE TABLE domain_audit_events (
	event_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT DEFAULT '' NOT NULL, 
	actor_user_id TEXT DEFAULT '' NOT NULL, 
	subject_user_id TEXT DEFAULT '' NOT NULL, 
	entity_type TEXT NOT NULL, 
	entity_id TEXT NOT NULL, 
	action TEXT NOT NULL, 
	before_json TEXT DEFAULT '{}' NOT NULL, 
	after_json TEXT DEFAULT '{}' NOT NULL, 
	reason TEXT DEFAULT '' NOT NULL, 
	correlation_id TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_domain_audit_events PRIMARY KEY (event_id)
);


CREATE TABLE domain_claim_versions (
	claim_version_id TEXT, 
	tenant_id TEXT NOT NULL, 
	claim_id TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	snapshot_json TEXT NOT NULL, 
	changed_by TEXT DEFAULT '' NOT NULL, 
	change_reason TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_domain_claim_versions PRIMARY KEY (claim_version_id), 
	CONSTRAINT uq_domain_claim_versions_1 UNIQUE (claim_id, version)
);


CREATE TABLE domain_claims (
	claim_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	owner_user_id TEXT NOT NULL, 
	source_type TEXT NOT NULL, 
	source_id TEXT NOT NULL, 
	source_locator TEXT DEFAULT '' NOT NULL, 
	claim_text TEXT NOT NULL, 
	normalized_text TEXT DEFAULT '' NOT NULL, 
	claim_type TEXT DEFAULT 'experience' NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	supersedes_claim_id TEXT DEFAULT '' NOT NULL, 
	created_by TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_domain_claims PRIMARY KEY (claim_id), 
	CONSTRAINT uq_domain_claims_1 UNIQUE (tenant_id, session_id, source_type, source_id, source_locator)
);


CREATE TABLE evidence_claims (
	claim_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	claim_text TEXT NOT NULL, 
	claim_type TEXT DEFAULT 'artifact_claim' NOT NULL, 
	status TEXT DEFAULT 'unverified' NOT NULL, 
	fingerprint TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	verification_status TEXT DEFAULT 'UNVERIFIED' NOT NULL, 
	verification_confidence FLOAT DEFAULT 0 NOT NULL, 
	verified_by TEXT DEFAULT '' NOT NULL, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	risk_level TEXT DEFAULT 'normal' NOT NULL, 
	requires_human_review INTEGER DEFAULT 0 NOT NULL, 
	CONSTRAINT pk_evidence_claims PRIMARY KEY (claim_id)
);


CREATE TABLE evidence_graph_edges (
	edge_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	from_type TEXT NOT NULL, 
	from_id TEXT NOT NULL, 
	relation TEXT NOT NULL, 
	to_type TEXT NOT NULL, 
	to_id TEXT NOT NULL, 
	confidence FLOAT DEFAULT 1.0 NOT NULL, 
	metadata_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_evidence_graph_edges PRIMARY KEY (edge_id), 
	CONSTRAINT uq_evidence_graph_edges_1 UNIQUE (tenant_id, from_type, from_id, relation, to_type, to_id)
);


CREATE TABLE evidence_item_verification_history (
	history_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	evidence_id TEXT NOT NULL, 
	previous_status TEXT NOT NULL, 
	new_status TEXT NOT NULL, 
	decision TEXT DEFAULT '' NOT NULL, 
	confidence FLOAT DEFAULT 0 NOT NULL, 
	method TEXT DEFAULT '' NOT NULL, 
	reason TEXT DEFAULT '' NOT NULL, 
	actor_user_id TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_evidence_item_verification_history PRIMARY KEY (history_id)
);


CREATE TABLE evidence_items (
	evidence_id TEXT, 
	session_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	owner_user_id TEXT DEFAULT '' NOT NULL, 
	source_type TEXT NOT NULL, 
	source_label TEXT NOT NULL, 
	content TEXT NOT NULL, 
	verified INTEGER DEFAULT 0 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	metadata_json TEXT DEFAULT '{}' NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	verification_status TEXT DEFAULT 'SELF_REPORTED' NOT NULL, 
	verification_method TEXT DEFAULT '' NOT NULL, 
	verification_confidence FLOAT DEFAULT 0 NOT NULL, 
	verified_by TEXT DEFAULT '' NOT NULL, 
	verified_at TIMESTAMP WITH TIME ZONE, 
	source_hash TEXT DEFAULT '' NOT NULL, 
	CONSTRAINT pk_evidence_items PRIMARY KEY (evidence_id)
);


CREATE TABLE evidence_verification_history (
	verification_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	claim_id TEXT NOT NULL, 
	previous_status TEXT DEFAULT 'UNVERIFIED' NOT NULL, 
	new_status TEXT NOT NULL, 
	confidence FLOAT DEFAULT 0 NOT NULL, 
	verifier_type TEXT DEFAULT 'ai' NOT NULL, 
	verified_by TEXT DEFAULT '' NOT NULL, 
	reason TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	risk_level TEXT DEFAULT 'normal' NOT NULL, 
	requires_human_review INTEGER DEFAULT 0 NOT NULL, 
	CONSTRAINT pk_evidence_verification_history PRIMARY KEY (verification_id)
);


CREATE TABLE job_requirement_capability_links (
	link_id TEXT, 
	tenant_id TEXT NOT NULL, 
	job_id TEXT NOT NULL, 
	requirement_id TEXT NOT NULL, 
	capability_id TEXT NOT NULL, 
	weight FLOAT DEFAULT 1 NOT NULL, 
	minimum_score FLOAT DEFAULT 60 NOT NULL, 
	mapping_status TEXT DEFAULT 'derived' NOT NULL, 
	explanation TEXT DEFAULT '' NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_job_requirement_capability_links PRIMARY KEY (link_id), 
	CONSTRAINT uq_job_requirement_capability_links_1 UNIQUE (tenant_id, requirement_id, capability_id)
);


CREATE TABLE job_requirement_versions (
	requirement_version_id TEXT, 
	tenant_id TEXT NOT NULL, 
	job_id TEXT NOT NULL, 
	requirement_id TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	snapshot_json TEXT NOT NULL, 
	changed_by TEXT DEFAULT '' NOT NULL, 
	change_reason TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_job_requirement_versions PRIMARY KEY (requirement_version_id), 
	CONSTRAINT uq_job_requirement_versions_1 UNIQUE (requirement_id, version)
);


CREATE TABLE job_requirements (
	requirement_id TEXT, 
	tenant_id TEXT NOT NULL, 
	job_id TEXT NOT NULL, 
	category TEXT DEFAULT 'requirement' NOT NULL, 
	requirement_text TEXT NOT NULL, 
	normalized_key TEXT DEFAULT '' NOT NULL, 
	importance INTEGER DEFAULT 3 NOT NULL, 
	source_type TEXT DEFAULT 'derived' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	version INTEGER DEFAULT 1 NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_job_requirements PRIMARY KEY (requirement_id)
);


CREATE TABLE jobs (
	job_id TEXT, 
	tenant_id TEXT DEFAULT 'global' NOT NULL, 
	title TEXT NOT NULL, 
	company TEXT DEFAULT '' NOT NULL, 
	city TEXT DEFAULT '' NOT NULL, 
	industry TEXT DEFAULT '' NOT NULL, 
	salary_min FLOAT, 
	salary_max FLOAT, 
	skills_json TEXT DEFAULT '[]' NOT NULL, 
	description TEXT DEFAULT '' NOT NULL, 
	source TEXT DEFAULT 'manual' NOT NULL, 
	source_url TEXT DEFAULT '' NOT NULL, 
	active INTEGER DEFAULT 1 NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_jobs PRIMARY KEY (job_id)
);


CREATE TABLE knowledge_embeddings (
	chunk_id TEXT, 
	source_id TEXT NOT NULL, 
	embedding_model TEXT NOT NULL, 
	embedding_version TEXT DEFAULT '1' NOT NULL, 
	vector_json TEXT NOT NULL, 
	content_hash TEXT DEFAULT '' NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	provider TEXT DEFAULT 'local_hash' NOT NULL, 
	dimensions INTEGER DEFAULT 0 NOT NULL, 
	warning TEXT DEFAULT '' NOT NULL, 
	CONSTRAINT pk_knowledge_embeddings PRIMARY KEY (chunk_id)
);


CREATE TABLE knowledge_sources (
	source_id TEXT, 
	tenant_id TEXT DEFAULT 'global' NOT NULL, 
	title TEXT NOT NULL, 
	filename TEXT NOT NULL, 
	mime_type TEXT DEFAULT '', 
	scope TEXT DEFAULT 'global' NOT NULL, 
	tags TEXT DEFAULT '[]' NOT NULL, 
	active INTEGER DEFAULT 1 NOT NULL, 
	char_count INTEGER DEFAULT 0 NOT NULL, 
	chunk_count INTEGER DEFAULT 0 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	category TEXT DEFAULT 'other' NOT NULL, 
	authority TEXT DEFAULT 'internal' NOT NULL, 
	effective_year TEXT DEFAULT '' NOT NULL, 
	priority INTEGER DEFAULT 50 NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_knowledge_sources PRIMARY KEY (source_id)
);


CREATE TABLE llm_model_capabilities (
	provider_id TEXT NOT NULL, 
	model TEXT NOT NULL, 
	supports_streaming INTEGER DEFAULT 0 NOT NULL, 
	supports_json_schema INTEGER DEFAULT 0 NOT NULL, 
	supports_tools INTEGER DEFAULT 0 NOT NULL, 
	supports_vision INTEGER DEFAULT 0 NOT NULL, 
	supports_files INTEGER DEFAULT 0 NOT NULL, 
	context_window INTEGER DEFAULT 0 NOT NULL, 
	max_output INTEGER DEFAULT 0 NOT NULL, 
	reasoning_level TEXT DEFAULT 'none' NOT NULL, 
	latency_class TEXT DEFAULT 'unknown' NOT NULL, 
	input_cost_per_million FLOAT DEFAULT 0 NOT NULL, 
	output_cost_per_million FLOAT DEFAULT 0 NOT NULL, 
	metadata_json TEXT DEFAULT '{}' NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_llm_model_capabilities PRIMARY KEY (provider_id, model)
);


CREATE TABLE llm_providers (
	provider_id TEXT, 
	name TEXT NOT NULL, 
	kind TEXT NOT NULL, 
	base_url TEXT NOT NULL, 
	api_key_enc TEXT DEFAULT '' NOT NULL, 
	default_model TEXT NOT NULL, 
	enabled INTEGER DEFAULT 1 NOT NULL, 
	timeout_seconds INTEGER DEFAULT 90 NOT NULL, 
	extra_headers TEXT DEFAULT '{}' NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_llm_providers PRIMARY KEY (provider_id)
);


CREATE TABLE llm_routes (
	task TEXT, 
	provider_id TEXT NOT NULL, 
	model TEXT NOT NULL, 
	fallback_provider_id TEXT, 
	fallback_model TEXT, 
	temperature FLOAT DEFAULT 0.2 NOT NULL, 
	max_tokens INTEGER DEFAULT 4000 NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_llm_routes PRIMARY KEY (task)
);


CREATE TABLE llm_usage (
	id SERIAL, 
	tenant_id TEXT DEFAULT 'global' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	task TEXT NOT NULL, 
	provider_id TEXT NOT NULL, 
	model TEXT NOT NULL, 
	input_tokens INTEGER DEFAULT 0, 
	output_tokens INTEGER DEFAULT 0, 
	total_tokens INTEGER DEFAULT 0, 
	latency_ms INTEGER DEFAULT 0, 
	success INTEGER DEFAULT 1 NOT NULL, 
	error TEXT DEFAULT '', 
	CONSTRAINT pk_llm_usage PRIMARY KEY (id)
);


CREATE TABLE model_eval_runs (
	eval_id TEXT, 
	tenant_id TEXT DEFAULT 'global' NOT NULL, 
	task TEXT DEFAULT 'evaluation' NOT NULL, 
	provider_id TEXT NOT NULL, 
	model TEXT NOT NULL, 
	metrics_json TEXT DEFAULT '{}' NOT NULL, 
	cases_json TEXT DEFAULT '[]' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_model_eval_runs PRIMARY KEY (eval_id)
);


CREATE TABLE plans (
	plan_id TEXT, 
	name TEXT NOT NULL, 
	entitlements_json TEXT DEFAULT '{}' NOT NULL, 
	active INTEGER DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_plans PRIMARY KEY (plan_id)
);


CREATE TABLE privacy_consents (
	consent_id TEXT, 
	tenant_id TEXT NOT NULL, 
	user_id TEXT NOT NULL, 
	policy_version TEXT NOT NULL, 
	purpose TEXT DEFAULT 'service' NOT NULL, 
	granted INTEGER DEFAULT 1 NOT NULL, 
	source TEXT DEFAULT 'ui' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_privacy_consents PRIMARY KEY (consent_id)
);


CREATE TABLE rag_eval_cases (
	case_id TEXT, 
	tenant_id TEXT DEFAULT 'global' NOT NULL, 
	query TEXT NOT NULL, 
	scope TEXT DEFAULT 'global' NOT NULL, 
	effective_year TEXT DEFAULT '' NOT NULL, 
	expected_source_id TEXT DEFAULT '' NOT NULL, 
	expected_authority TEXT DEFAULT '' NOT NULL, 
	notes TEXT DEFAULT '' NOT NULL, 
	active INTEGER DEFAULT 1 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_rag_eval_cases PRIMARY KEY (case_id)
);


CREATE TABLE rag_eval_runs (
	run_id TEXT, 
	tenant_id TEXT DEFAULT 'global' NOT NULL, 
	metrics_json TEXT DEFAULT '{}' NOT NULL, 
	cases_json TEXT DEFAULT '[]' NOT NULL, 
	embedding_model TEXT DEFAULT '' NOT NULL, 
	retrieval_mode TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_rag_eval_runs PRIMARY KEY (run_id)
);


CREATE TABLE review_records (
	review_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	artifact_id TEXT DEFAULT '' NOT NULL, 
	version_id TEXT DEFAULT '' NOT NULL, 
	total_score INTEGER, 
	report_json TEXT DEFAULT '{}' NOT NULL, 
	created_by TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_review_records PRIMARY KEY (review_id)
);


CREATE TABLE schema_migrations (
	version SERIAL, 
	name TEXT NOT NULL, 
	applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_schema_migrations PRIMARY KEY (version)
);


CREATE TABLE security_audit_log (
	audit_id SERIAL, 
	tenant_id TEXT DEFAULT 'global' NOT NULL, 
	user_id TEXT DEFAULT '' NOT NULL, 
	action TEXT NOT NULL, 
	resource_type TEXT DEFAULT '' NOT NULL, 
	resource_id TEXT DEFAULT '' NOT NULL, 
	success INTEGER DEFAULT 1 NOT NULL, 
	details_json TEXT DEFAULT '{}' NOT NULL, 
	ip_address TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_security_audit_log PRIMARY KEY (audit_id)
);


CREATE TABLE sessions (
	session_id TEXT, 
	payload TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	student_user_id TEXT DEFAULT '' NOT NULL, 
	class_id TEXT DEFAULT 'default' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_sessions PRIMARY KEY (session_id)
);


CREATE TABLE stored_objects (
	object_id TEXT, 
	tenant_id TEXT NOT NULL, 
	owner_user_id TEXT DEFAULT '' NOT NULL, 
	session_id TEXT DEFAULT '' NOT NULL, 
	provider TEXT NOT NULL, 
	object_key TEXT NOT NULL, 
	filename TEXT NOT NULL, 
	content_type TEXT DEFAULT '' NOT NULL, 
	size_bytes INTEGER DEFAULT 0 NOT NULL, 
	sha256 TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	status TEXT DEFAULT 'active' NOT NULL, 
	scan_status TEXT DEFAULT 'unknown' NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_stored_objects PRIMARY KEY (object_id)
);


CREATE TABLE teacher_feedback (
	feedback_id TEXT, 
	session_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	teacher_user_id TEXT DEFAULT '' NOT NULL, 
	teacher_name TEXT DEFAULT 'Advisor' NOT NULL, 
	content TEXT NOT NULL, 
	priority TEXT DEFAULT 'normal' NOT NULL, 
	status TEXT DEFAULT 'open' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_teacher_feedback PRIMARY KEY (feedback_id)
);


CREATE TABLE tenant_subscriptions (
	tenant_id TEXT, 
	plan_id TEXT DEFAULT 'free' NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	billing_provider TEXT DEFAULT 'mock' NOT NULL, 
	external_customer_id TEXT DEFAULT '' NOT NULL, 
	external_subscription_id TEXT DEFAULT '' NOT NULL, 
	current_period_end TIMESTAMP WITH TIME ZONE, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_tenant_subscriptions PRIMARY KEY (tenant_id)
);


CREATE TABLE tenants (
	tenant_id TEXT, 
	name TEXT NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	branding_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	tenant_type TEXT DEFAULT 'organization' NOT NULL, 
	product_preset TEXT DEFAULT 'career_development' NOT NULL, 
	settings_json TEXT DEFAULT '{}' NOT NULL, 
	CONSTRAINT pk_tenants PRIMARY KEY (tenant_id)
);


CREATE TABLE unified_runtime_entities (
	tenant_id TEXT NOT NULL, 
	owner_user_id TEXT DEFAULT '' NOT NULL, 
	entity_type TEXT NOT NULL, 
	entity_id TEXT NOT NULL, 
	payload_json TEXT DEFAULT '{}' NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	revision INTEGER DEFAULT 0 NOT NULL, 
	updated_by TEXT DEFAULT '' NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_unified_runtime_entities PRIMARY KEY (tenant_id, owner_user_id, entity_type, entity_id)
);


CREATE TABLE unified_runtime_revisions (
	tenant_id TEXT, 
	revision INTEGER DEFAULT 0 NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_unified_runtime_revisions PRIMARY KEY (tenant_id)
);


CREATE TABLE user_invitations (
	invitation_id TEXT, 
	token_hash TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	email TEXT NOT NULL, 
	role TEXT NOT NULL, 
	display_name TEXT DEFAULT '' NOT NULL, 
	invited_by TEXT DEFAULT '' NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_user_invitations PRIMARY KEY (invitation_id), 
	CONSTRAINT uq_user_invitations_1 UNIQUE (token_hash)
);


CREATE TABLE users (
	user_id TEXT, 
	email TEXT NOT NULL, 
	password_hash TEXT NOT NULL, 
	display_name TEXT DEFAULT '' NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_users PRIMARY KEY (user_id), 
	CONSTRAINT uq_users_1 UNIQUE (email)
);


CREATE TABLE workflow_instances (
	workflow_id TEXT, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	current_step_id TEXT DEFAULT 'self_exploration' NOT NULL, 
	progress INTEGER DEFAULT 0 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	template_id TEXT DEFAULT 'career_development_v1' NOT NULL, 
	CONSTRAINT pk_workflow_instances PRIMARY KEY (workflow_id), 
	CONSTRAINT uq_workflow_instances_1 UNIQUE (session_id)
);


CREATE TABLE workflow_template_definitions (
	template_id TEXT, 
	tenant_id TEXT NOT NULL, 
	preset_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	status TEXT DEFAULT 'draft' NOT NULL, 
	definition_json TEXT DEFAULT '{}' NOT NULL, 
	created_by TEXT DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_workflow_template_definitions PRIMARY KEY (template_id)
);


CREATE TABLE artifact_versions (
	version_id TEXT, 
	artifact_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	source TEXT DEFAULT 'unknown' NOT NULL, 
	created_by TEXT DEFAULT '' NOT NULL, 
	metadata_json TEXT DEFAULT '{}' NOT NULL, 
	evidence_links_json TEXT DEFAULT '[]' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_artifact_versions PRIMARY KEY (version_id), 
	CONSTRAINT uq_artifact_versions_1 UNIQUE (artifact_id, version), 
	CONSTRAINT fk_artifact_versions_1_artifact_id FOREIGN KEY(artifact_id) REFERENCES artifact_series (artifact_id)
);


CREATE TABLE auth_sessions (
	auth_session_id TEXT, 
	token_hash TEXT NOT NULL, 
	user_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	role TEXT NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_auth_sessions PRIMARY KEY (auth_session_id), 
	CONSTRAINT uq_auth_sessions_1 UNIQUE (token_hash), 
	CONSTRAINT fk_auth_sessions_1_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id), 
	CONSTRAINT fk_auth_sessions_2_user_id FOREIGN KEY(user_id) REFERENCES users (user_id)
);


CREATE TABLE classes (
	class_id TEXT, 
	tenant_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_classes PRIMARY KEY (class_id), 
	CONSTRAINT uq_classes_1 UNIQUE (tenant_id, name), 
	CONSTRAINT fk_classes_1_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id)
);


CREATE TABLE knowledge_chunks (
	chunk_id TEXT, 
	source_id TEXT NOT NULL, 
	chunk_index INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	content_hash TEXT DEFAULT '' NOT NULL, 
	embedding_model TEXT DEFAULT '' NOT NULL, 
	CONSTRAINT pk_knowledge_chunks PRIMARY KEY (chunk_id), 
	CONSTRAINT fk_knowledge_chunks_1_source_id FOREIGN KEY(source_id) REFERENCES knowledge_sources (source_id) ON DELETE CASCADE
);


CREATE TABLE password_reset_tokens (
	reset_id TEXT, 
	token_hash TEXT NOT NULL, 
	user_id TEXT NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	used_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_password_reset_tokens PRIMARY KEY (reset_id), 
	CONSTRAINT uq_password_reset_tokens_1 UNIQUE (token_hash), 
	CONSTRAINT fk_password_reset_tokens_1_user_id FOREIGN KEY(user_id) REFERENCES users (user_id)
);


CREATE TABLE project_templates (
	template_id TEXT, 
	tenant_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	category TEXT DEFAULT 'career_planning' NOT NULL, 
	status TEXT DEFAULT 'draft' NOT NULL, 
	current_version_id TEXT, 
	created_by TEXT DEFAULT '' NOT NULL, 
	created_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_project_templates PRIMARY KEY (template_id), 
	CONSTRAINT uq_project_templates_1 UNIQUE (template_id, tenant_id), 
	CONSTRAINT fk_project_templates_1_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE
);


CREATE TABLE tenant_memberships (
	membership_id TEXT, 
	tenant_id TEXT NOT NULL, 
	user_id TEXT NOT NULL, 
	role TEXT NOT NULL, 
	status TEXT DEFAULT 'active' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_tenant_memberships PRIMARY KEY (membership_id), 
	CONSTRAINT uq_tenant_memberships_1 UNIQUE (tenant_id, user_id, role), 
	CONSTRAINT fk_tenant_memberships_1_user_id FOREIGN KEY(user_id) REFERENCES users (user_id), 
	CONSTRAINT fk_tenant_memberships_2_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id)
);


CREATE TABLE workflow_steps (
	workflow_step_id TEXT, 
	workflow_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	step_id TEXT NOT NULL, 
	step_index INTEGER NOT NULL, 
	label TEXT NOT NULL, 
	status TEXT DEFAULT 'locked' NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	completed_by TEXT DEFAULT '' NOT NULL, 
	source_type TEXT DEFAULT '' NOT NULL, 
	source_id TEXT DEFAULT '' NOT NULL, 
	metadata_json TEXT DEFAULT '{}' NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_workflow_steps PRIMARY KEY (workflow_step_id), 
	CONSTRAINT uq_workflow_steps_1 UNIQUE (workflow_id, step_id), 
	CONSTRAINT fk_workflow_steps_1_workflow_id FOREIGN KEY(workflow_id) REFERENCES workflow_instances (workflow_id)
);


CREATE TABLE class_memberships (
	class_membership_id TEXT, 
	class_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	user_id TEXT NOT NULL, 
	role TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT pk_class_memberships PRIMARY KEY (class_membership_id), 
	CONSTRAINT uq_class_memberships_1 UNIQUE (class_id, user_id, role), 
	CONSTRAINT fk_class_memberships_1_user_id FOREIGN KEY(user_id) REFERENCES users (user_id), 
	CONSTRAINT fk_class_memberships_2_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (tenant_id), 
	CONSTRAINT fk_class_memberships_3_class_id FOREIGN KEY(class_id) REFERENCES classes (class_id)
);


CREATE TABLE project_template_versions (
	template_version_id TEXT, 
	template_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	name TEXT NOT NULL, 
	category TEXT NOT NULL, 
	description TEXT DEFAULT '' NOT NULL, 
	background TEXT DEFAULT '' NOT NULL, 
	objective TEXT DEFAULT '' NOT NULL, 
	applicable_users TEXT DEFAULT '' NOT NULL, 
	estimated_time_minutes INTEGER DEFAULT 60 NOT NULL, 
	output_type TEXT DEFAULT 'career_report' NOT NULL, 
	questions_json TEXT DEFAULT '[]' NOT NULL, 
	material_requirements_json TEXT DEFAULT '[]' NOT NULL, 
	artifact_structure_json TEXT DEFAULT '[]' NOT NULL, 
	rubric_json TEXT DEFAULT '{}' NOT NULL, 
	workflow_template_id TEXT NOT NULL, 
	artifact_template_id TEXT DEFAULT 'career_report_v1' NOT NULL, 
	status TEXT DEFAULT 'published' NOT NULL, 
	published_at TEXT, 
	created_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_project_template_versions PRIMARY KEY (template_version_id), 
	CONSTRAINT uq_project_template_versions_1 UNIQUE (template_id, version), 
	CONSTRAINT uq_project_template_versions_2 UNIQUE (template_version_id, tenant_id), 
	CONSTRAINT fk_project_template_versions_1_template_id FOREIGN KEY(template_id) REFERENCES project_templates (template_id) ON DELETE RESTRICT
);


CREATE TABLE project_instances (
	project_id TEXT, 
	tenant_id TEXT NOT NULL, 
	owner_user_id TEXT NOT NULL, 
	template_id TEXT NOT NULL, 
	template_version_id TEXT NOT NULL, 
	session_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	status TEXT DEFAULT 'draft' NOT NULL, 
	current_step TEXT DEFAULT 'overview' NOT NULL, 
	current_artifact_id TEXT, 
	current_artifact_version_id TEXT, 
	latest_score_run_id TEXT, 
	created_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	completed_at TEXT, 
	CONSTRAINT pk_project_instances PRIMARY KEY (project_id), 
	CONSTRAINT uq_project_instances_1 UNIQUE (project_id, tenant_id), 
	CONSTRAINT fk_project_instances_1_template_id FOREIGN KEY(template_id) REFERENCES project_templates (template_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_project_instances_2_template_version_id FOREIGN KEY(template_version_id) REFERENCES project_template_versions (template_version_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_project_instances_3_session_id FOREIGN KEY(session_id) REFERENCES sessions (session_id) ON DELETE RESTRICT
);


CREATE TABLE project_answers (
	project_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	owner_user_id TEXT NOT NULL, 
	question_id TEXT NOT NULL, 
	answer_json TEXT DEFAULT 'null' NOT NULL, 
	created_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT pk_project_answers PRIMARY KEY (project_id, question_id), 
	CONSTRAINT fk_project_answers_1_project_id FOREIGN KEY(project_id) REFERENCES project_instances (project_id) ON DELETE CASCADE
);

CREATE INDEX idx_tasks_tenant ON ai_tasks (tenant_id, status, updated_at);
CREATE INDEX idx_tasks_owner_active ON ai_tasks (tenant_id, owner_user_id, status, updated_at);
CREATE INDEX idx_analytics_tenant_time ON analytics_events (tenant_id, created_at);
CREATE INDEX idx_artifact_series_session ON artifact_series (tenant_id, session_id, updated_at);
CREATE INDEX idx_artifact_owner_active ON artifact_series (tenant_id, owner_user_id, deleted_at, updated_at);
CREATE INDEX idx_artifact_template_defs_tenant ON artifact_template_definitions (tenant_id, kind, status, version);
CREATE INDEX idx_billing_events_tenant ON billing_events (tenant_id, received_at);
CREATE INDEX idx_billing_events_provider ON billing_events (provider, received_at);
CREATE INDEX idx_billing_orders_tenant ON billing_orders (tenant_id, created_at);
CREATE INDEX idx_capabilities_tenant_category ON capabilities (tenant_id, category, status, name);
CREATE INDEX idx_assessment_evidence_assessment ON capability_assessment_evidence (tenant_id, assessment_id);
CREATE INDEX idx_capability_assessments_latest ON capability_assessments (tenant_id, session_id, capability_id, assessment_version);
CREATE INDEX idx_capability_versions_tenant ON capability_versions (tenant_id, capability_id, version);
CREATE INDEX idx_career_gap_versions_tenant ON career_gap_versions (tenant_id, gap_id, version);
CREATE INDEX idx_career_gaps_session_job ON career_gaps (tenant_id, session_id, job_id, status, severity);
CREATE INDEX idx_claim_capability_capability ON claim_capability_links (tenant_id, capability_id, confidence);
CREATE INDEX idx_claim_evidence_evidence ON claim_evidence_links (tenant_id, evidence_id, relation);
CREATE INDEX idx_claim_evidence_claim ON claim_evidence_links (tenant_id, claim_id, relation, confidence);
CREATE INDEX idx_data_subject_requests_user ON data_subject_requests (tenant_id, user_id, created_at);
CREATE INDEX idx_domain_audit_session ON domain_audit_events (tenant_id, session_id, created_at);
CREATE INDEX idx_domain_audit_entity ON domain_audit_events (tenant_id, entity_type, entity_id, created_at);
CREATE INDEX idx_domain_claim_versions_tenant ON domain_claim_versions (tenant_id, claim_id, version);
CREATE INDEX idx_domain_claims_session ON domain_claims (tenant_id, session_id, owner_user_id, status, updated_at);
CREATE INDEX idx_claims_session ON evidence_claims (tenant_id, session_id, created_at);
CREATE INDEX idx_graph_edges_session ON evidence_graph_edges (tenant_id, session_id, created_at);
CREATE INDEX idx_evidence_item_verification_history ON evidence_item_verification_history (tenant_id, evidence_id, created_at);
CREATE INDEX idx_evidence_session ON evidence_items (session_id, created_at);
CREATE INDEX idx_evidence_verification ON evidence_items (tenant_id, owner_user_id, verification_status, updated_at);
CREATE INDEX idx_evidence_tenant_session ON evidence_items (tenant_id, session_id, created_at);
CREATE INDEX idx_evidence_owner_active ON evidence_items (tenant_id, owner_user_id, deleted_at, updated_at);
CREATE INDEX idx_verification_history_claim ON evidence_verification_history (tenant_id, claim_id, created_at);
CREATE INDEX idx_verification_history_session ON evidence_verification_history (tenant_id, session_id, created_at);
CREATE INDEX idx_requirement_capability_job ON job_requirement_capability_links (tenant_id, job_id, requirement_id);
CREATE INDEX idx_job_requirement_versions ON job_requirement_versions (tenant_id, job_id, requirement_id, version);
CREATE INDEX idx_job_requirements_job ON job_requirements (tenant_id, job_id, importance);
CREATE INDEX idx_jobs_tenant ON jobs (tenant_id, active, updated_at);
CREATE INDEX idx_jobs_title_city ON jobs (title, city, active);
CREATE INDEX idx_knowledge_embeddings_source ON knowledge_embeddings (source_id);
CREATE INDEX idx_knowledge_sources_scope ON knowledge_sources (scope, active);
CREATE INDEX idx_knowledge_tenant ON knowledge_sources (tenant_id, updated_at);
CREATE INDEX idx_knowledge_sources_tenant ON knowledge_sources (tenant_id, active, updated_at);
CREATE INDEX idx_llm_model_capabilities_provider ON llm_model_capabilities (provider_id, updated_at);
CREATE INDEX idx_llm_usage_tenant ON llm_usage (tenant_id, created_at);
CREATE INDEX idx_model_eval_runs_tenant ON model_eval_runs (tenant_id, created_at);
CREATE INDEX idx_privacy_consents_user ON privacy_consents (tenant_id, user_id, created_at);
CREATE INDEX idx_rag_eval_cases_tenant ON rag_eval_cases (tenant_id, active, created_at);
CREATE INDEX idx_rag_eval_runs_tenant ON rag_eval_runs (tenant_id, created_at);
CREATE INDEX idx_review_records_session ON review_records (tenant_id, session_id, created_at);
CREATE INDEX idx_security_audit_tenant ON security_audit_log (tenant_id, created_at);
CREATE INDEX idx_sessions_owner ON sessions (student_user_id, tenant_id);
CREATE INDEX idx_sessions_class ON sessions (tenant_id, class_id, updated_at);
CREATE INDEX idx_sessions_tenant_updated ON sessions (tenant_id, updated_at);
CREATE INDEX idx_stored_objects_status ON stored_objects (tenant_id, status, created_at);
CREATE INDEX idx_stored_objects_tenant_owner ON stored_objects (tenant_id, owner_user_id, created_at);
CREATE INDEX idx_feedback_tenant_session ON teacher_feedback (tenant_id, session_id, created_at);
CREATE INDEX idx_feedback_session ON teacher_feedback (session_id, created_at);
CREATE INDEX idx_unified_runtime_tenant_type_updated ON unified_runtime_entities (tenant_id, entity_type, updated_at);
CREATE INDEX idx_unified_runtime_tenant_type_revision ON unified_runtime_entities (tenant_id, entity_type, revision);
CREATE INDEX idx_unified_runtime_owner ON unified_runtime_entities (tenant_id, owner_user_id, entity_type, revision);
CREATE INDEX idx_user_invitations_tenant ON user_invitations (tenant_id, created_at);
CREATE INDEX idx_user_invitations_email ON user_invitations (email, tenant_id);
CREATE INDEX idx_workflow_session ON workflow_instances (tenant_id, session_id);
CREATE INDEX idx_workflow_template ON workflow_instances (tenant_id, template_id, updated_at);
CREATE INDEX idx_workflow_template_defs_tenant ON workflow_template_definitions (tenant_id, preset_id, status, version);
CREATE INDEX idx_artifact_versions_series ON artifact_versions (artifact_id, version);
CREATE INDEX idx_artifact_versions_tenant ON artifact_versions (tenant_id, artifact_id, version);
CREATE INDEX idx_auth_sessions_token ON auth_sessions (token_hash);
CREATE INDEX idx_auth_sessions_tenant ON auth_sessions (tenant_id, user_id, expires_at);
CREATE INDEX idx_knowledge_chunks_source ON knowledge_chunks (source_id);
CREATE INDEX idx_project_templates_tenant_status ON project_templates (tenant_id, status, updated_at);
CREATE INDEX idx_memberships_user ON tenant_memberships (user_id, tenant_id);
CREATE INDEX idx_workflow_steps_session ON workflow_steps (tenant_id, session_id, step_index);
CREATE INDEX idx_class_memberships_user ON class_memberships (user_id, tenant_id);
CREATE INDEX idx_project_template_versions_tenant_template ON project_template_versions (tenant_id, template_id, version);
CREATE INDEX idx_project_instances_tenant_owner_status ON project_instances (tenant_id, owner_user_id, status, updated_at);
CREATE INDEX idx_project_instances_tenant_template ON project_instances (tenant_id, template_version_id);
CREATE INDEX idx_project_answers_tenant_owner_project ON project_answers (tenant_id, owner_user_id, project_id);
