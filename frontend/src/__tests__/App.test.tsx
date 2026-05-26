import { render, screen } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import LandingPage from '../LandingPage';

test('renders app successfully', () => {
  render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>
  );
  expect(screen.getByText(/Veritrace/i)).toBeInTheDocument();
});
