-- Online Bookstore System: sample catalog
-- Run after schema.sql: mysql -u root -p < db/seed.sql
--
-- Prices and stock levels are made up for the demo.
-- Book 5 has zero stock on purpose, to demonstrate out-of-stock handling.
-- User accounts are created through the API in Week 3, so that passwords are
-- hashed by the application and no credentials are kept in this file.

USE online_bookstore;

INSERT INTO categories (id, name) VALUES
    (1, 'Programming'),
    (2, 'Computer Science'),
    (3, 'Classic Fiction'),
    (4, 'Science Fiction & Fantasy'),
    (5, 'Non-Fiction');

INSERT INTO authors (id, name) VALUES
    (1,  'Robert C. Martin'),
    (2,  'Erich Gamma'),
    (3,  'Richard Helm'),
    (4,  'Ralph Johnson'),
    (5,  'John Vlissides'),
    (6,  'Eric Freeman'),
    (7,  'Elisabeth Robson'),
    (8,  'David Thomas'),
    (9,  'Andrew Hunt'),
    (10, 'Joshua Bloch'),
    (11, 'Luciano Ramalho'),
    (12, 'Thomas H. Cormen'),
    (13, 'Charles E. Leiserson'),
    (14, 'Ronald L. Rivest'),
    (15, 'Clifford Stein'),
    (16, 'Jane Austen'),
    (17, 'George Orwell'),
    (18, 'Harper Lee'),
    (19, 'J.R.R. Tolkien'),
    (20, 'Frank Herbert'),
    (21, 'Yuval Noah Harari'),
    (22, 'Daniel Kahneman');

INSERT INTO books (id, isbn, title, description, price, stock, category_id) VALUES
    (1,  '9780132350884', 'Clean Code', 'Practical principles for writing readable, maintainable software.', 44.99, 25, 1),
    (2,  '9780201633610', 'Design Patterns: Elements of Reusable Object-Oriented Software', 'The classic catalog of 23 object-oriented design patterns.', 54.99, 12, 1),
    (3,  '9781492078005', 'Head First Design Patterns, 2nd Edition', 'A visual, beginner-friendly introduction to design patterns.', 59.99, 18, 1),
    (4,  '9780135957059', 'The Pragmatic Programmer, 20th Anniversary Edition', 'Career-long habits and techniques for software developers.', 49.99, 20, 1),
    (5,  '9780134685991', 'Effective Java, 3rd Edition', 'Best practices for the Java programming language.', 52.99, 0, 1),
    (6,  '9781492056355', 'Fluent Python, 2nd Edition', 'A deep guide to writing idiomatic Python.', 69.99, 15, 1),
    (7,  '9780262046305', 'Introduction to Algorithms, 4th Edition', 'A comprehensive textbook on algorithms and data structures.', 99.99, 8, 2),
    (8,  '9780141439518', 'Pride and Prejudice', 'A novel of manners, marriage and misunderstanding in Regency England.', 9.99, 40, 3),
    (9,  '9780451524935', 'Nineteen Eighty-Four', 'A dystopian novel about surveillance and totalitarian rule.', 10.99, 35, 3),
    (10, '9780061120084', 'To Kill a Mockingbird', 'A story of childhood, racial injustice and conscience in the American South.', 12.99, 30, 3),
    (11, '9780547928227', 'The Hobbit', 'A reluctant hero sets out on a quest with a company of dwarves.', 13.99, 28, 4),
    (12, '9780441172719', 'Dune', 'Politics, religion and ecology collide on a desert planet.', 11.99, 22, 4),
    (13, '9780062316097', 'Sapiens: A Brief History of Humankind', 'A sweeping account of human history.', 18.99, 26, 5),
    (14, '9780374533557', 'Thinking, Fast and Slow', 'How two systems of thought shape our judgment and decisions.', 17.99, 24, 5);

INSERT INTO book_authors (book_id, author_id, author_position) VALUES
    (1, 1, 1),
    (2, 2, 1), (2, 3, 2), (2, 4, 3), (2, 5, 4),
    (3, 6, 1), (3, 7, 2),
    (4, 8, 1), (4, 9, 2),
    (5, 10, 1),
    (6, 11, 1),
    (7, 12, 1), (7, 13, 2), (7, 14, 3), (7, 15, 4),
    (8, 16, 1),
    (9, 17, 1),
    (10, 18, 1),
    (11, 19, 1),
    (12, 20, 1),
    (13, 21, 1),
    (14, 22, 1);
