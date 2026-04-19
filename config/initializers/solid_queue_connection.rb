Rails.application.config.after_initialize do

  SolidQueue::Process.establish_connection(
    ActiveRecord::Base.connection_db_config
  )
end
