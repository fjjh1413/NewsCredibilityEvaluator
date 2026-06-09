ALTER TABLE detection_records
    ADD COLUMN review_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '审核状态：pending/approved/rejected',
    ADD COLUMN is_public TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否允许前台公开展示',
    ADD COLUMN admin_remark TEXT NULL COMMENT '管理员内部审核备注',
    ADD COLUMN reviewed_at DATETIME NULL COMMENT '审核时间',
    ADD COLUMN reviewed_by BIGINT NULL COMMENT '审核管理员ID';

UPDATE detection_records
SET is_high_risk = 1
WHERE final_score < 40 OR risk_level = '高风险谣言';

UPDATE detection_records
SET review_status = 'pending', is_public = 0
WHERE is_high_risk = 1;

ALTER TABLE detection_records
    ADD INDEX idx_detection_review_status (review_status),
    ADD INDEX idx_detection_is_public (is_public),
    ADD INDEX idx_detection_reviewed_by (reviewed_by),
    ADD CONSTRAINT fk_detection_reviewed_by
        FOREIGN KEY (reviewed_by) REFERENCES users(id)
        ON DELETE SET NULL;
