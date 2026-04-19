class AddProcessedAtToRecordings < ActiveRecord::Migration[8.1]
  def change
    add_column :recordings, :processed_at, :datetime
  end
end
