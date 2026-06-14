INSERT INTO plans (id, name, version, is_active, is_custom_pricing)
VALUES ('00000000-0000-0000-0000-000000000001', 'free', 1, true, false)
ON CONFLICT DO NOTHING;

INSERT INTO plan_pricing (family_id, plan_version, amount, currency)
VALUES ('00000000-0000-0000-0000-000000000001', 1, 0, 'NGN')
ON CONFLICT DO NOTHING;

INSERT INTO plan_entitlements (family_id, plan_version, feature_key, value) VALUES
('00000000-0000-0000-0000-000000000001', 1, 'request_quota',       '{"type": "numeric", "limit": 1000}'),
('00000000-0000-0000-0000-000000000001', 1, 'active_projects',     '{"type": "numeric", "limit": 1}'),
('00000000-0000-0000-0000-000000000001', 1, 'security_scanning',   '{"type": "boolean", "enabled": false}'),
('00000000-0000-0000-0000-000000000001', 1, 'jailbreak_detection', '{"type": "boolean", "enabled": false}'),
('00000000-0000-0000-0000-000000000001', 1, 'pii_masking',         '{"type": "boolean", "enabled": false}'),
('00000000-0000-0000-0000-000000000001', 1, 'caching',             '{"type": "boolean", "enabled": false}'),
('00000000-0000-0000-0000-000000000001', 1, 'observability',       '{"type": "boolean", "enabled": false}')
ON CONFLICT DO NOTHING;


INSERT INTO plans (id, name, version, is_active, is_custom_pricing)
VALUES ('00000000-0000-0000-0000-000000000002', 'pro', 1, true, false)
ON CONFLICT DO NOTHING;

INSERT INTO plan_pricing (family_id, plan_version, amount, currency)
VALUES ('00000000-0000-0000-0000-000000000002', 1, 3900000, 'NGN')
ON CONFLICT DO NOTHING;

INSERT INTO plan_entitlements (family_id, plan_version, feature_key, value) VALUES
('00000000-0000-0000-0000-000000000002', 1, 'request_quota',       '{"type": "numeric", "limit": 50000}'),
('00000000-0000-0000-0000-000000000002', 1, 'active_projects',     '{"type": "numeric", "limit": -1}'),
('00000000-0000-0000-0000-000000000002', 1, 'security_scanning',   '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000002', 1, 'jailbreak_detection', '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000002', 1, 'pii_masking',         '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000002', 1, 'caching',             '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000002', 1, 'observability',       '{"type": "boolean", "enabled": true}')
ON CONFLICT DO NOTHING;


INSERT INTO plans (id, name, version, is_active, is_custom_pricing)
VALUES ('00000000-0000-0000-0000-000000000003', 'team', 1, true, false)
ON CONFLICT DO NOTHING;

INSERT INTO plan_pricing (family_id, plan_version, amount, currency)
VALUES ('00000000-0000-0000-0000-000000000003', 1, 15000000, 'NGN')
ON CONFLICT DO NOTHING;

INSERT INTO plan_entitlements (family_id, plan_version, feature_key, value) VALUES
('00000000-0000-0000-0000-000000000003', 1, 'request_quota',       '{"type": "numeric", "limit": 250000}'),
('00000000-0000-0000-0000-000000000003', 1, 'active_projects',     '{"type": "numeric", "limit": -1}'),
('00000000-0000-0000-0000-000000000003', 1, 'security_scanning',   '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000003', 1, 'jailbreak_detection', '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000003', 1, 'pii_masking',         '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000003', 1, 'caching',             '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000003', 1, 'observability',       '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000003', 1, 'team_seats',          '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000003', 1, 'end_user_billing',    '{"type": "boolean", "enabled": true}')
ON CONFLICT DO NOTHING;


INSERT INTO plans (id, name, version, is_active, is_custom_pricing)
VALUES ('00000000-0000-0000-0000-000000000004', 'enterprise', 1, true, true)
ON CONFLICT DO NOTHING;

INSERT INTO plan_entitlements (family_id, plan_version, feature_key, value) VALUES
('00000000-0000-0000-0000-000000000004', 1, 'request_quota',       '{"type": "numeric", "limit": -1}'),
('00000000-0000-0000-0000-000000000004', 1, 'active_projects',     '{"type": "numeric", "limit": -1}'),
('00000000-0000-0000-0000-000000000004', 1, 'security_scanning',   '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000004', 1, 'jailbreak_detection', '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000004', 1, 'pii_masking',         '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000004', 1, 'caching',             '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000004', 1, 'observability',       '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000004', 1, 'team_seats',          '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000004', 1, 'end_user_billing',    '{"type": "boolean", "enabled": true}'),
('00000000-0000-0000-0000-000000000004', 1, 'custom_sla',          '{"type": "boolean", "enabled": true}')
ON CONFLICT DO NOTHING;
