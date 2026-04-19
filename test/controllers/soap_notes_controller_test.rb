require "test_helper"

class SoapNotesControllerTest < ActionDispatch::IntegrationTest
  test "should get show" do
    get soap_notes_show_url
    assert_response :success
  end

  test "should get create" do
    get soap_notes_create_url
    assert_response :success
  end
end
