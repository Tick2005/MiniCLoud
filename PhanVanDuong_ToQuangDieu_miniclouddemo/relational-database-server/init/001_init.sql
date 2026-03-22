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
