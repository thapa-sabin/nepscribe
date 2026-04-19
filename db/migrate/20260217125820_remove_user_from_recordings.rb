class RemoveUserFromRecordings < ActiveRecord::Migration[8.1]
  def change
    remove_reference :recordings, :user, null: false, foreign_key: true
  end
end
