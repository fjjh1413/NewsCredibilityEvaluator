-- MySQL dump 10.13  Distrib 8.4.10, for Linux (x86_64)
--
-- Host: localhost    Database: zhiyun_bianzhen
-- ------------------------------------------------------
-- Server version	8.4.10

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('0007_analysis_payload');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `crawl_tasks`
--

DROP TABLE IF EXISTS `crawl_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `crawl_tasks` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `job_name` varchar(100) NOT NULL,
  `search_query` varchar(500) NOT NULL,
  `freshness` varchar(50) NOT NULL,
  `total_found` int NOT NULL DEFAULT '0',
  `new_added` int NOT NULL DEFAULT '0',
  `duplicates` int NOT NULL DEFAULT '0',
  `fetch_failed` int NOT NULL DEFAULT '0',
  `errors` text,
  `started_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `finished_at` datetime DEFAULT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'running',
  PRIMARY KEY (`id`),
  KEY `idx_crawl_tasks_job` (`job_name`),
  KEY `idx_crawl_tasks_time` (`started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `crawl_tasks`
--

LOCK TABLES `crawl_tasks` WRITE;
/*!40000 ALTER TABLE `crawl_tasks` DISABLE KEYS */;
/*!40000 ALTER TABLE `crawl_tasks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `detection_records`
--

DROP TABLE IF EXISTS `detection_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `detection_records` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint DEFAULT NULL,
  `input_title` varchar(255) NOT NULL,
  `input_content` text NOT NULL,
  `category` varchar(50) DEFAULT NULL,
  `keywords` varchar(500) DEFAULT NULL,
  `final_score` decimal(5,2) NOT NULL,
  `evidence_score` decimal(5,2) NOT NULL,
  `llm_score` decimal(5,2) NOT NULL,
  `rule_score` decimal(5,2) NOT NULL,
  `risk_level` varchar(30) NOT NULL,
  `judgement_result` varchar(100) NOT NULL,
  `reason` text,
  `risk_points` text,
  `suggestion` text,
  `is_high_risk` tinyint(1) NOT NULL DEFAULT '0',
  `report_url` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `review_status` varchar(20) NOT NULL DEFAULT 'pending',
  `is_public` tinyint(1) NOT NULL DEFAULT '0',
  `admin_remark` text,
  `reviewed_at` datetime DEFAULT NULL,
  `reviewed_by` bigint DEFAULT NULL,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `analysis_payload` text,
  PRIMARY KEY (`id`),
  KEY `idx_detection_user_id` (`user_id`),
  KEY `idx_detection_risk_level` (`risk_level`),
  KEY `idx_detection_is_high_risk` (`is_high_risk`),
  KEY `idx_detection_created_at` (`created_at`),
  KEY `idx_detection_review_status` (`review_status`),
  KEY `idx_detection_is_public` (`is_public`),
  KEY `idx_detection_reviewed_by` (`reviewed_by`),
  CONSTRAINT `detection_records_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_detection_reviewed_by` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `detection_records`
--

LOCK TABLES `detection_records` WRITE;
/*!40000 ALTER TABLE `detection_records` DISABLE KEYS */;
/*!40000 ALTER TABLE `detection_records` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `evidence_matches`
--

DROP TABLE IF EXISTS `evidence_matches`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `evidence_matches` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `detection_id` bigint NOT NULL,
  `knowledge_id` bigint DEFAULT NULL,
  `title` varchar(255) NOT NULL,
  `summary` text,
  `source_name` varchar(100) DEFAULT NULL,
  `similarity_score` decimal(6,4) NOT NULL,
  `rank_order` int NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `url` varchar(500) DEFAULT NULL,
  `origin` varchar(20) NOT NULL DEFAULT 'knowledge',
  PRIMARY KEY (`id`),
  KEY `idx_evidence_detection_id` (`detection_id`),
  KEY `idx_evidence_knowledge_id` (`knowledge_id`),
  KEY `idx_evidence_origin` (`origin`),
  CONSTRAINT `evidence_matches_ibfk_1` FOREIGN KEY (`detection_id`) REFERENCES `detection_records` (`id`) ON DELETE CASCADE,
  CONSTRAINT `evidence_matches_ibfk_2` FOREIGN KEY (`knowledge_id`) REFERENCES `knowledge_items` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `evidence_matches`
--

LOCK TABLES `evidence_matches` WRITE;
/*!40000 ALTER TABLE `evidence_matches` DISABLE KEYS */;
/*!40000 ALTER TABLE `evidence_matches` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `knowledge_items`
--

DROP TABLE IF EXISTS `knowledge_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `knowledge_items` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `content` text NOT NULL,
  `category` varchar(50) DEFAULT NULL,
  `truth_label` varchar(30) NOT NULL,
  `source_name` varchar(100) DEFAULT NULL,
  `source_url` varchar(500) DEFAULT NULL,
  `publish_time` datetime DEFAULT NULL,
  `summary` text,
  `keywords` varchar(500) DEFAULT NULL,
  `debunking_explanation` text,
  `risk_level` varchar(30) DEFAULT NULL,
  `admin_note` text,
  `vector_id` varchar(100) DEFAULT NULL,
  `vector_sync_status` varchar(20) NOT NULL DEFAULT 'pending',
  `vector_sync_error` text,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_category` (`category`),
  KEY `idx_truth_label` (`truth_label`),
  KEY `idx_risk_level` (`risk_level`),
  KEY `idx_vector_sync_status` (`vector_sync_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `knowledge_items`
--

LOCK TABLES `knowledge_items` WRITE;
/*!40000 ALTER TABLE `knowledge_items` DISABLE KEYS */;
/*!40000 ALTER TABLE `knowledge_items` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `prompt_templates`
--

DROP TABLE IF EXISTS `prompt_templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `prompt_templates` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `type` varchar(50) NOT NULL,
  `content` text NOT NULL,
  `is_default` tinyint(1) NOT NULL DEFAULT '0',
  `status` varchar(20) NOT NULL DEFAULT 'enabled',
  `created_by` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_prompt_type` (`type`),
  KEY `idx_prompt_status` (`status`),
  KEY `idx_prompt_type_default` (`type`,`is_default`),
  KEY `idx_prompt_created_by` (`created_by`),
  CONSTRAINT `prompt_templates_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `prompt_templates`
--

LOCK TABLES `prompt_templates` WRITE;
/*!40000 ALTER TABLE `prompt_templates` DISABLE KEYS */;
/*!40000 ALTER TABLE `prompt_templates` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `reports`
--

DROP TABLE IF EXISTS `reports`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `reports` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `detection_id` bigint NOT NULL,
  `user_id` bigint DEFAULT NULL,
  `report_title` varchar(255) NOT NULL,
  `html_path` varchar(500) DEFAULT NULL,
  `pdf_path` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_reports_detection_id` (`detection_id`),
  KEY `idx_report_user_id` (`user_id`),
  CONSTRAINT `reports_ibfk_1` FOREIGN KEY (`detection_id`) REFERENCES `detection_records` (`id`) ON DELETE CASCADE,
  CONSTRAINT `reports_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `reports`
--

LOCK TABLES `reports` WRITE;
/*!40000 ALTER TABLE `reports` DISABLE KEYS */;
/*!40000 ALTER TABLE `reports` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `system_logs`
--

DROP TABLE IF EXISTS `system_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_logs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint DEFAULT NULL,
  `action` varchar(100) NOT NULL,
  `module` varchar(100) NOT NULL,
  `description` text,
  `ip_address` varchar(50) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_system_log_user_id` (`user_id`),
  KEY `idx_system_log_module` (`module`),
  KEY `idx_system_log_action` (`action`),
  KEY `idx_system_log_created_at` (`created_at`),
  CONSTRAINT `system_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `system_logs`
--

LOCK TABLES `system_logs` WRITE;
/*!40000 ALTER TABLE `system_logs` DISABLE KEYS */;
/*!40000 ALTER TABLE `system_logs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `email` varchar(100) DEFAULT NULL,
  `role` varchar(20) NOT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'admin','$2b$12$fgEaxgKthNd4yaLMw2xe8O/uYYZiordkW4p.Z6vxGmWBQ4WjMbAeu','admin@example.com','admin','active','2026-07-06 09:37:27','2026-07-06 09:37:27');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping routines for database 'zhiyun_bianzhen'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-07-06 10:46:53
