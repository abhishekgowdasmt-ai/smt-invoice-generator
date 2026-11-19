\set ON_ERROR_STOP on
BEGIN;

INSERT INTO branches (code, name, city)
VALUES ('BLR', 'Bengaluru', 'Bengaluru');

INSERT INTO branches (code, name, city)
VALUES ('HYD', 'Hyderabad', 'Hyderabad');

COMMIT;
