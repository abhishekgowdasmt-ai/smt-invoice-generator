import { Sequelize } from 'sequelize';
import dotenv from 'dotenv';

dotenv.config();

// Use DATABASE_URL if available (Docker), otherwise use individual config
let sequelize;

const useSsl =
  process.env.DATABASE_SSL === 'true' ||
  process.env.PGSSLMODE === 'require' ||
  process.env.NODE_ENV === 'production';

const common = {
  dialect: 'postgres',
  logging: process.env.NODE_ENV === 'development' ? console.log : false,
  pool: {
    max: 5,
    min: 0,
    acquire: 30000,
    idle: 10000
  },
  dialectOptions: useSsl
    ? { ssl: { require: true, rejectUnauthorized: false } }
    : {}
};

if (process.env.DATABASE_URL) {
  sequelize = new Sequelize(process.env.DATABASE_URL, common);
} else {
  sequelize = new Sequelize({
    host: process.env.DB_HOST || 'localhost',
    port: process.env.DB_PORT || 5432,
    database: process.env.DB_NAME || 'postgres',
    username: process.env.DB_USER || 'postgres',
    password: process.env.DB_PASSWORD || 'postgres',
    ...common
  });
}

export default sequelize;
