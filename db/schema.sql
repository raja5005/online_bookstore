-- Online Bookstore System: MySQL 8 schema
-- Run with: mysql -u root -p < db/schema.sql
--
-- To rebuild from scratch, drop the database first:
--   DROP DATABASE online_bookstore;

CREATE DATABASE IF NOT EXISTS online_bookstore
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE online_bookstore;

-- ---------------------------------------------------------------------------
-- Users (created through UserFactory; `role` selects the user type)
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email         VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(120) NOT NULL,
    role          ENUM('CUSTOMER', 'ADMIN') NOT NULL DEFAULT 'CUSTOMER',
    is_active     BOOLEAN  NOT NULL DEFAULT TRUE,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_email UNIQUE (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Catalog
-- ---------------------------------------------------------------------------
CREATE TABLE categories (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    CONSTRAINT uq_categories_name UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE authors (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    CONSTRAINT uq_authors_name UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE books (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    isbn        CHAR(13)      NOT NULL,
    title       VARCHAR(255)  NOT NULL,
    description TEXT          NULL,
    price       DECIMAL(10,2) NOT NULL,
    stock       INT           NOT NULL DEFAULT 0,
    category_id INT           NOT NULL,
    cover_url   VARCHAR(500)  NULL,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_books_isbn UNIQUE (isbn),
    CONSTRAINT fk_books_category FOREIGN KEY (category_id) REFERENCES categories (id),
    CONSTRAINT ck_books_isbn  CHECK (isbn REGEXP '^[0-9]{13}$'),
    CONSTRAINT ck_books_price CHECK (price >= 0),
    CONSTRAINT ck_books_stock CHECK (stock >= 0),
    INDEX idx_books_title (title),
    INDEX idx_books_active_category (is_active, category_id)
) ENGINE=InnoDB;

-- Junction table: a book can have several authors, in a defined order.
CREATE TABLE book_authors (
    book_id         INT     NOT NULL,
    author_id       INT     NOT NULL,
    author_position TINYINT NOT NULL DEFAULT 1,
    PRIMARY KEY (book_id, author_id),
    CONSTRAINT fk_book_authors_book   FOREIGN KEY (book_id)   REFERENCES books (id)   ON DELETE CASCADE,
    CONSTRAINT fk_book_authors_author FOREIGN KEY (author_id) REFERENCES authors (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Shopping cart (one per user)
-- ---------------------------------------------------------------------------
CREATE TABLE carts (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT      NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_carts_user UNIQUE (user_id),
    CONSTRAINT fk_carts_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE cart_items (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    cart_id  INT      NOT NULL,
    book_id  INT      NOT NULL,
    quantity INT      NOT NULL,
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_cart_items_cart_book UNIQUE (cart_id, book_id),
    CONSTRAINT fk_cart_items_cart FOREIGN KEY (cart_id) REFERENCES carts (id) ON DELETE CASCADE,
    CONSTRAINT fk_cart_items_book FOREIGN KEY (book_id) REFERENCES books (id),
    CONSTRAINT ck_cart_items_quantity CHECK (quantity > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Orders (`status` is driven by the State pattern)
-- ---------------------------------------------------------------------------
CREATE TABLE orders (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT           NOT NULL,
    status           ENUM('PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED')
                                   NOT NULL DEFAULT 'PENDING',
    total_amount     DECIMAL(10,2) NOT NULL,
    shipping_address VARCHAR(500)  NOT NULL,
    created_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT ck_orders_total CHECK (total_amount >= 0),
    INDEX idx_orders_user_created (user_id, created_at),
    INDEX idx_orders_status (status)
) ENGINE=InnoDB;

-- unit_price is a copy of the price at purchase time, so later price changes
-- never alter past orders.
CREATE TABLE order_items (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    order_id   INT           NOT NULL,
    book_id    INT           NOT NULL,
    quantity   INT           NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    CONSTRAINT uq_order_items_order_book UNIQUE (order_id, book_id),
    CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders (id),
    CONSTRAINT fk_order_items_book  FOREIGN KEY (book_id)  REFERENCES books (id),
    CONSTRAINT ck_order_items_quantity CHECK (quantity > 0),
    CONSTRAINT ck_order_items_price    CHECK (unit_price >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Payments (`method` selects the Strategy; one row per attempt)
-- No card numbers or other payment credentials are stored.
-- ---------------------------------------------------------------------------
CREATE TABLE payments (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT           NOT NULL,
    method          ENUM('CREDIT_CARD', 'PAYPAL', 'BANK_TRANSFER') NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    status          ENUM('SUCCESS', 'FAILED', 'REFUNDED') NOT NULL,
    transaction_ref VARCHAR(64)   NULL,
    failure_reason  VARCHAR(255)  NULL,
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_payments_transaction_ref UNIQUE (transaction_ref),
    CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders (id),
    CONSTRAINT ck_payments_amount CHECK (amount > 0),
    INDEX idx_payments_order (order_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Order status audit trail (changed_by is NULL for automatic system changes)
-- ---------------------------------------------------------------------------
CREATE TABLE order_status_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT NOT NULL,
    from_status ENUM('PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED') NULL,
    to_status   ENUM('PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED') NOT NULL,
    changed_by  INT NULL,
    note        VARCHAR(255) NULL,
    changed_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_history_order FOREIGN KEY (order_id)   REFERENCES orders (id),
    CONSTRAINT fk_history_user  FOREIGN KEY (changed_by) REFERENCES users (id),
    INDEX idx_history_order (order_id, changed_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Notifications (written by the Observer pattern's in-app subscriber)
-- ---------------------------------------------------------------------------
CREATE TABLE notifications (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL,
    order_id   INT NULL,
    type       ENUM('ORDER_PLACED', 'ORDER_PAID', 'ORDER_SHIPPED',
                    'ORDER_DELIVERED', 'ORDER_CANCELLED') NOT NULL,
    message    VARCHAR(500) NOT NULL,
    is_read    BOOLEAN  NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_user  FOREIGN KEY (user_id)  REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_notifications_order FOREIGN KEY (order_id) REFERENCES orders (id),
    INDEX idx_notifications_user_read (user_id, is_read)
) ENGINE=InnoDB;
