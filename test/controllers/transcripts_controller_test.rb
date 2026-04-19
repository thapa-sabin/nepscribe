require "test_helper"

class TranscriptsControllerTest < ActionDispatch::IntegrationTest
  test "should get show" do
    get transcripts_show_url
    assert_response :success
  end
end
