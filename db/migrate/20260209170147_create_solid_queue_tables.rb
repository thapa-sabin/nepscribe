class CreateSolidQueueTables < ActiveRecord::Migration[8.1]
  def change
    create_table :solid_queue_processes, if_not_exists: true do |t|
      t.string :queue
      t.string :handler
      t.integer :priority, default: 0
      t.text :arguments
      t.datetime :run_at
      t.timestamps
    end
  end
end
