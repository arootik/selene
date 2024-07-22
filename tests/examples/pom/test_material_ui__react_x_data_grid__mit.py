import pytest

import selene
from selene import browser, have, be, command, query
from selene.support._pom import Element, All


class DataGridMIT:
    grid = Element('[role=grid]')

    header = grid.element('.MuiDataGrid-columnHeaders')
    toggle_all_checkbox = header.element('.PrivateSwitchBase-input')
    '''
    # todo: support also the following:
    toggle_all = headers.ElementBy(have.attribute('data-field').value('__check__'))
    toggle_all_checkbox = toggle_all.Element('[type=checkbox]')
    '''
    column_headers = grid.all('[role=columnheader]')

    footer = Element('.MuiDataGrid-footerContainer')
    selected_rows_count = footer.element('.MuiDataGrid-selectedRowCount')
    pagination = footer.element('.MuiTablePagination-root')
    pagination_rows_displayed = pagination.element('.MuiTablePagination-displayedRows')
    page_to_right = pagination.element('[data-testid=KeyboardArrowRightIcon]')
    page_to_left = pagination.element('[data-testid=KeyboardArrowLeftIcon]')

    content = grid.element('[role=rowgroup]')
    rows = content.all('[role=row]')
    _cells_selector = '[role=gridcell]'
    cells = content.all(_cells_selector)
    editing_cell_input = content.element('.MuiDataGrid-cell--editing').element('input')

    def __init__(self, context: selene.Element):
        self.context = context

    def cells_of_row(self, number, /):
        return self.rows[number - 1].all(self._cells_selector)

    # todo: support int for column
    def cell(self, *, row, column_data_field=None, column=None):
        if column:
            column_data_field = self.column_headers.element_by(
                have.exact_text(column)
            ).get(query.attribute('data-field'))

        return self.cells_of_row(row).element_by(
            have.attribute('data-field').value(column_data_field)
        )

    def set_cell(self, *, row, column_data_field=None, column=None, to_text):
        self.cell(
            row=row, column_data_field=column_data_field, column=column
        ).double_click()
        self.editing_cell_input.perform(command.select_all).type(to_text).press_enter()


@pytest.mark.parametrize(
    'characters',
    [
        DataGridMIT(
            browser.with_(timeout=2.0).element('#DataGridDemo+* .MuiDataGrid-root')
        ),
    ],
)
def test_material_ui__react_x_data_grid_mit(characters):
    browser.driver.refresh()

    # WHEN
    browser.open('https://mui.com/x/react-data-grid/#DataGridDemo')

    # THEN
    # - check headers
    characters.column_headers.should(have.size(6))
    characters.column_headers.should(
        have._exact_texts_like(
            {...}, 'ID', 'First name', 'Last name', 'Age', 'Full name'
        )
    )

    # - pagination works
    characters.pagination_rows_displayed.should(have.exact_text('1–5 of 9'))
    characters.page_to_right.click()
    characters.pagination_rows_displayed.should(have.exact_text('6–9 of 9'))
    characters.page_to_left.click()
    characters.pagination_rows_displayed.should(have.exact_text('1–5 of 9'))

    # - toggle all works to select all rows
    characters.selected_rows_count.should(be.not_.visible)
    characters.toggle_all_checkbox.should(be.not_.checked)
    characters.toggle_all_checkbox.click()
    characters.toggle_all_checkbox.should(be.checked)
    characters.selected_rows_count.should(have.exact_text('9 rows selected'))
    characters.toggle_all_checkbox.click()
    characters.toggle_all_checkbox.should(be.not_.checked)
    characters.selected_rows_count.should(be.not_.visible)

    # - check rows
    characters.rows.should(have.size(5))
    characters.cells_of_row(1).should(
        have._exact_texts_like({...}, {...}, 'Jon', 'Snow', '14', 'Jon Snow')
    )

    # - sorting works
    # TODO: implement

    # - filtering works
    # TODO: implement

    # - hiding works
    # TODO: implement

    # - a cell can be edited
    characters.set_cell(row=1, column_data_field='firstName', to_text='John')
    characters.cells_of_row(1).should(
        have._exact_texts_like({...}, {...}, 'John', 'Snow', '14', 'John Snow')
    )
    characters.set_cell(row=1, column='First name', to_text='Jon')
    characters.cells_of_row(1).should(
        have._exact_texts_like({...}, {...}, 'Jon', 'Snow', '14', 'Jon Snow')
    )
