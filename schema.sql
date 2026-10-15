CREATE TABLE IF NOT EXISTS schema_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS users(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, username varchar(80) NOT NULL UNIQUE,password_hash text NOT NULL);
CREATE TABLE IF NOT EXISTS categories(id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,name varchar(80) NOT NULL CHECK(length(trim(name))>0));
CREATE UNIQUE INDEX IF NOT EXISTS category_name_unique ON categories(lower(name));
CREATE TABLE IF NOT EXISTS products(
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 sku varchar(40) NOT NULL UNIQUE CHECK(length(trim(sku))>0),
 name varchar(120) NOT NULL CHECK(length(trim(name))>0),
 price numeric(12,2) NOT NULL CHECK(price>=0),
 category_id bigint NOT NULL REFERENCES categories(id),
 quantity integer NOT NULL DEFAULT 0 CHECK(quantity BETWEEN 0 AND 100000000),
 low_stock_threshold integer NOT NULL DEFAULT 5 CHECK(low_stock_threshold BETWEEN 0 AND 1000000)
);
CREATE TABLE IF NOT EXISTS movements(
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 product_id bigint NOT NULL REFERENCES products(id),user_id bigint NOT NULL REFERENCES users(id),
 kind varchar(10) NOT NULL CHECK(kind IN ('receive','sale')),
 quantity integer NOT NULL CHECK(quantity BETWEEN 1 AND 1000000),
 balance_after integer NOT NULL CHECK(balance_after>=0),unit_price numeric(12,2) NOT NULL CHECK(unit_price>=0),
 note varchar(200) NOT NULL DEFAULT '',request_id uuid NOT NULL UNIQUE,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS movements_product ON movements(product_id,id DESC);
CREATE TABLE IF NOT EXISTS login_attempts(username varchar(80) NOT NULL,happened_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS login_attempts_lookup ON login_attempts(username,happened_at);
INSERT INTO schema_migrations(version) VALUES(1) ON CONFLICT DO NOTHING;
