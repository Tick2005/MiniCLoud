CREATE DATABASE IF NOT EXISTS minicloud;
USE minicloud;
CREATE TABLE IF NOT EXISTS notes(
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO notes(title) VALUES ('Hello from MariaDB!');

CREATE DATABASE IF NOT EXISTS studentdb;
USE studentdb;
CREATE TABLE IF NOT EXISTS students(
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id VARCHAR(10) NOT NULL,
    fullname VARCHAR(100) NOT NULL,
    dob DATE NOT NULL,
    major VARCHAR(50) NOT NULL
);

INSERT INTO students(student_id, fullname, dob, major)
SELECT 'SV001', 'Nguyen Van A', '2002-03-15', 'Computer Science'
WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = 'SV001');

INSERT INTO students(student_id, fullname, dob, major)
SELECT 'SV002', 'Tran Thi B', '2001-11-02', 'Data Science'
WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = 'SV002');

INSERT INTO students(student_id, fullname, dob, major)
SELECT 'SV003', 'Le Van C', '2002-07-20', 'Cybersecurity'
WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = 'SV003');

CREATE TABLE IF NOT EXISTS blog_comments(
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_name VARCHAR(100) NOT NULL,
    author_name VARCHAR(100) NOT NULL,
    comment_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blog_likes(
    id INT AUTO_INCREMENT PRIMARY KEY,
    article_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO blog_likes (article_name)
SELECT 'blog1' WHERE NOT EXISTS (
    SELECT 1 FROM blog_likes WHERE article_name = 'blog1'
);

INSERT INTO blog_likes (article_name)
SELECT 'blog2' WHERE NOT EXISTS (
    SELECT 1 FROM blog_likes WHERE article_name = 'blog2'
);

INSERT INTO blog_likes (article_name)
SELECT 'blog3' WHERE NOT EXISTS (
    SELECT 1 FROM blog_likes WHERE article_name = 'blog3'
);

INSERT INTO blog_comments (article_name, author_name, comment_text)
SELECT 'blog1', 'Alice', 'Great breakdown of why short feedback loops matter in cloud practice.'
WHERE NOT EXISTS (
    SELECT 1 FROM blog_comments
    WHERE article_name = 'blog1' AND author_name = 'Alice'
);

INSERT INTO blog_comments (article_name, author_name, comment_text)
SELECT 'blog2', 'Martin', 'This is a useful reminder that rest can improve engineering quality.'
WHERE NOT EXISTS (
    SELECT 1 FROM blog_comments
    WHERE article_name = 'blog2' AND author_name = 'Martin'
);

INSERT INTO blog_comments (article_name, author_name, comment_text)
SELECT 'blog3', 'Nora', 'The artifact-first approach really changed how I track my progress.'
WHERE NOT EXISTS (
    SELECT 1 FROM blog_comments
    WHERE article_name = 'blog3' AND author_name = 'Nora'
);
