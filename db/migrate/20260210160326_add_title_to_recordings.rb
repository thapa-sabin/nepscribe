class AddTitleToRecordings < ActiveRecord::Migration[8.1]
  def change
    add_column :recordings, :title, :string
  end
end
