import sequelize from '../src/config/database.js';

const migrate = async () => {
  try {
    console.log('🚀 Running database migrations...');

    // Sync all models (creates tables if they don't exist)
    await sequelize.sync({ alter: process.env.NODE_ENV === 'development' });

    console.log('✅ Database migrations completed!');
    process.exit(0);
  } catch (err) {
    console.error('❌ Migration failed:', err.message);
    process.exit(1);
  }
};

migrate();
