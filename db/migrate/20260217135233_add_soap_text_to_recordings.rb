class AddSoapTextToRecordings < ActiveRecord::Migration[8.1]
  def change
    add_column :recordings, :soap_text, :text
  end
end
