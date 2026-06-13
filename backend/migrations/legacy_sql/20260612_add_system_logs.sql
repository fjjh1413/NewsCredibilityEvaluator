CREATE TABLE IF NOT EXISTS system_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '日志ID',
    user_id BIGINT DEFAULT NULL COMMENT '用户ID',
    action VARCHAR(100) NOT NULL COMMENT '操作动作',
    module VARCHAR(100) NOT NULL COMMENT '所属模块',
    description TEXT DEFAULT NULL COMMENT '操作描述',
    ip_address VARCHAR(50) DEFAULT NULL COMMENT 'IP地址',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_system_log_user_id (user_id),
    INDEX idx_system_log_module (module),
    INDEX idx_system_log_action (action),
    INDEX idx_system_log_created_at (created_at),
    CONSTRAINT fk_system_log_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统日志表';
