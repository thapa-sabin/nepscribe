Rails.application.routes.draw do
  root "recordings#new"

  resources :recordings, only: [:new, :create, :show] do
    resource :soap_note, only: [:show, :edit, :update]  # singular resource for 1:1 relationship
  end
end

