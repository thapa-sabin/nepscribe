class CreateSoapNotes < ActiveRecord::Migration[8.1]
  def change
    create_table :soap_notes do |t|
      t.references :recording, null: false, foreign_key: true
      t.text :subjective
      t.text :objective
      t.text :assessment
      t.text :plan

      t.timestamps
    end
  end
end
