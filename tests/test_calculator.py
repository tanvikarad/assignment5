import datetime
import os
from pathlib import Path
import pandas as pd
import pytest
from unittest.mock import Mock, patch, PropertyMock
from decimal import Decimal
from tempfile import TemporaryDirectory
from app.calculation import Calculation
from app.calculator import Calculator
from app.calculator_memento import CalculatorMemento
from app.calculator_repl import calculator_repl
from app.calculator_config import CalculatorConfig
from app.exceptions import OperationError, ValidationError
from app.history import LoggingObserver, AutoSaveObserver
from app.operations import OperationFactory


@pytest.fixture(autouse=True)
def isolate_calculator_env(monkeypatch):
    for var in [
        'CALCULATOR_BASE_DIR',
        'CALCULATOR_LOG_DIR',
        'CALCULATOR_HISTORY_DIR',
        'CALCULATOR_HISTORY_FILE',
        'CALCULATOR_LOG_FILE',
        'CALCULATOR_MAX_HISTORY_SIZE',
        'CALCULATOR_AUTO_SAVE',
        'CALCULATOR_PRECISION',
        'CALCULATOR_MAX_INPUT_VALUE',
        'CALCULATOR_DEFAULT_ENCODING',
    ]:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def isolated_repl_calculator(monkeypatch):
    with TemporaryDirectory() as temp_dir:
        class IsolatedCalculator(Calculator):
            def __init__(self):
                super().__init__(config=CalculatorConfig(base_dir=Path(temp_dir)))

        monkeypatch.setattr('app.calculator_repl.Calculator', IsolatedCalculator)
        yield

# Fixture to initialize Calculator with a temporary directory for file paths
@pytest.fixture
def calculator():
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = CalculatorConfig(base_dir=temp_path)

        # Patch properties to use the temporary directory paths
        with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
             patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file, \
             patch.object(CalculatorConfig, 'history_dir', new_callable=PropertyMock) as mock_history_dir, \
             patch.object(CalculatorConfig, 'history_file', new_callable=PropertyMock) as mock_history_file:
            
            # Set return values to use paths within the temporary directory
            mock_log_dir.return_value = temp_path / "logs"
            mock_log_file.return_value = temp_path / "logs/calculator.log"
            mock_history_dir.return_value = temp_path / "history"
            mock_history_file.return_value = temp_path / "history/calculator_history.csv"
            
            # Return an instance of Calculator with the mocked config
            yield Calculator(config=config)

# Test Calculator Initialization

def test_calculator_initialization(calculator):
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []
    assert calculator.operation_strategy is None

# Test Logging Setup

@patch('app.calculator.logging.info')
def test_logging_setup(logging_info_mock):
    with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
         patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file:
        mock_log_dir.return_value = Path('/tmp/logs')
        mock_log_file.return_value = Path('/tmp/logs/calculator.log')
        
        # Instantiate calculator to trigger logging
        calculator = Calculator(CalculatorConfig())
        logging_info_mock.assert_any_call("Calculator initialized with configuration")

# Test Adding and Removing Observers

def test_add_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    assert observer in calculator.observers

def test_remove_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    calculator.remove_observer(observer)
    assert observer not in calculator.observers

# Test Setting Operations

def test_set_operation(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    assert calculator.operation_strategy == operation

# Test Performing Operations

def test_perform_operation_addition(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    result = calculator.perform_operation(2, 3)
    assert result == Decimal('5')

def test_perform_operation_validation_error(calculator):
    calculator.set_operation(OperationFactory.create_operation('add'))
    with pytest.raises(ValidationError):
        calculator.perform_operation('invalid', 3)

def test_perform_operation_operation_error(calculator):
    with pytest.raises(OperationError, match="No operation set"):
        calculator.perform_operation(2, 3)

# Test Undo/Redo Functionality

def test_undo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    assert calculator.history == []

def test_redo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    calculator.redo()
    assert len(calculator.history) == 1

# Test History Management

@patch('app.calculator.pd.DataFrame.to_csv')
def test_save_history(mock_to_csv, calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.save_history()
    mock_to_csv.assert_called_once()

@patch('app.calculator.pd.read_csv')
@patch('app.calculator.Path.exists', return_value=True)
def test_load_history(mock_exists, mock_read_csv, calculator):
    # Mock CSV data to match the expected format in from_dict
    mock_read_csv.return_value = pd.DataFrame({
        'operation': ['Addition'],
        'operand1': ['2'],
        'operand2': ['3'],
        'result': ['5'],
        'timestamp': [datetime.datetime.now().isoformat()]
    })
    
    # Test the load_history functionality
    try:
        calculator.load_history()
        # Verify history length after loading
        assert len(calculator.history) == 1
        # Verify the loaded values
        assert calculator.history[0].operation == "Addition"
        assert calculator.history[0].operand1 == Decimal("2")
        assert calculator.history[0].operand2 == Decimal("3")
        assert calculator.history[0].result == Decimal("5")
    except OperationError:
        pytest.fail("Loading history failed due to OperationError")
        
            
# Test Clearing History

def test_clear_history(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.clear_history()
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []

# Test REPL Commands (using patches for input/output handling)

@patch('builtins.input', side_effect=['exit'])
@patch('builtins.print')
def test_calculator_repl_exit(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history') as mock_save_history:
        calculator_repl()
        mock_save_history.assert_called_once()
        mock_print.assert_any_call("History saved successfully.")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['help', 'exit'])
@patch('builtins.print')
def test_calculator_repl_help(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nAvailable commands:")

@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_addition(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nResult: 5")


def test_calculation_error_paths_and_serialization():
    calc = Calculation(operation='Addition', operand1=Decimal('2'), operand2=Decimal('3'))
    assert calc.result == Decimal('5')
    assert calc.to_dict()['result'] == '5'
    assert str(calc) == 'Addition(2, 3) = 5'
    assert calc == Calculation(operation='Addition', operand1=Decimal('2'), operand2=Decimal('3'))
    assert calc != 'not-a-calculation'
    assert 'result=5' in repr(calc)
    assert calc.format_result(2) == '5'

    with pytest.raises(OperationError, match='Unknown operation'):
        Calculation(operation='Modulo', operand1=Decimal('2'), operand2=Decimal('3'))

    with pytest.raises(OperationError, match='Calculation failed'):
        Calculation(operation='Addition', operand1=Decimal('sNaN'), operand2=Decimal('1'))

    with pytest.raises(OperationError, match='Division by zero is not allowed'):
        Calculation(operation='Division', operand1=Decimal('5'), operand2=Decimal('0'))

    with pytest.raises(OperationError, match='Negative exponents are not supported'):
        Calculation(operation='Power', operand1=Decimal('5'), operand2=Decimal('-1'))

    with pytest.raises(OperationError, match='Zero root is undefined'):
        Calculation(operation='Root', operand1=Decimal('8'), operand2=Decimal('0'))

    with pytest.raises(OperationError, match='Cannot calculate root of negative number'):
        Calculation(operation='Root', operand1=Decimal('-8'), operand2=Decimal('2'))

    bad_data = {
        'operation': 'Addition',
        'operand1': '2',
        'operand2': '3',
        'result': '99',
        'timestamp': '2024-01-01T00:00:00'
    }
    with patch('app.calculation.logging.warning') as warning_mock:
        restored = Calculation.from_dict(bad_data)
        warning_mock.assert_called_once()
        assert restored.result == Decimal('5')

    with pytest.raises(OperationError, match='Invalid calculation data'):
        Calculation.from_dict({'operation': 'Addition', 'operand1': 'bad', 'operand2': '3', 'result': '5', 'timestamp': 'bad'})

    calc.result = Decimal('NaN')
    assert calc.format_result(2) == 'NaN'
    other = Calculation(operation='Addition', operand1=Decimal('5'), operand2=Decimal('7'))
    other.result = Decimal('NaN')
    assert calc != other
    assert calc.__eq__(None) is NotImplemented


def test_calculator_history_and_memento_paths():
    with TemporaryDirectory() as temp_dir:
        config = CalculatorConfig(base_dir=Path(temp_dir))
        calculator = Calculator(config=config)

        assert calculator.get_history_dataframe().empty
        assert calculator.show_history() == []

        calculator.set_operation(OperationFactory.create_operation('add'))
        calculator.perform_operation(2, 3)
        calculator.perform_operation(4, 5)

        assert len(calculator.history) == 2
        assert calculator.get_history_dataframe().shape[0] == 2
        assert calculator.show_history()[0].startswith('Addition')

        assert calculator.undo() is True
        assert len(calculator.history) == 1
        assert calculator.redo() is True
        assert len(calculator.history) == 2
        assert calculator.undo() is True
        assert len(calculator.history) == 1
        assert calculator.undo() is True
        assert calculator.undo() is False
        assert calculator.redo() is True
        assert calculator.redo() is True
        assert calculator.redo() is False

        calculator.clear_history()
        assert calculator.history == []
        assert calculator.undo_stack == []
        assert calculator.redo_stack == []

        calculator.save_history()
        assert calculator.config.history_file.exists()

        empty = Calculator(config=config)
        empty.clear_history()
        empty.save_history()

        with patch.object(Path, 'exists', return_value=False):
            empty.load_history()

        memento = CalculatorMemento(history=calculator.history.copy())
        payload = memento.to_dict()
        restored = CalculatorMemento.from_dict(payload)
        assert restored.history == calculator.history


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['help', 'exit'])
@patch('builtins.print')
def test_calculator_repl_help_and_exit_paths(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nAvailable commands:")
    mock_print.assert_any_call("Goodbye!")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['history', 'exit'])
@patch('builtins.print')
def test_calculator_repl_history_and_clear(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("No calculations in history")
    mock_print.assert_any_call("Goodbye!")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['clear', 'exit'])
@patch('builtins.print')
def test_calculator_repl_clear_command(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("History cleared")
    mock_print.assert_any_call("Goodbye!")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['undo', 'redo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_undo_redo_empty(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("Nothing to undo")
    mock_print.assert_any_call("Nothing to redo")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['save', 'exit'])
@patch('builtins.print')
def test_calculator_repl_save_command(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("History saved successfully")
    mock_print.assert_any_call("Goodbye!")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['load', 'exit'])
@patch('builtins.print')
def test_calculator_repl_load_command(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("History loaded successfully")
    mock_print.assert_any_call("Goodbye!")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['add', 'cancel', 'exit'])
@patch('builtins.print')
def test_calculator_repl_operation_cancel(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("Operation cancelled")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['unknown', 'exit'])
@patch('builtins.print')
def test_calculator_repl_unknown_command(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("Unknown command: 'unknown'. Type 'help' for available commands.")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['add', '2', 'bad', 'exit'])
@patch('builtins.print')
def test_calculator_repl_operation_error(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("Error: Invalid number format: bad")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=[KeyboardInterrupt(), EOFError()])
@patch('builtins.print')
def test_calculator_repl_interrupt_and_eof(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nOperation cancelled")
    mock_print.assert_any_call("\nInput terminated. Exiting...")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['exit'])
@patch('builtins.print')
def test_calculator_repl_exit_warning(mock_print, mock_input):
    with patch('app.calculator_repl.Calculator.save_history', side_effect=RuntimeError('disk failure')):
        calculator_repl()
    mock_print.assert_any_call("Warning: Could not save history: disk failure")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_unexpected_error(mock_print, mock_input):
    with patch('app.calculator_repl.OperationFactory.create_operation', side_effect=RuntimeError('factory boom')):
        calculator_repl()
    mock_print.assert_any_call("Unexpected error: factory boom")


def test_calculator_repl_fatal_error(capsys):
    with patch('app.calculator_repl.Calculator', side_effect=RuntimeError('init boom')):
        with pytest.raises(RuntimeError, match='init boom'):
            calculator_repl()
    assert 'Fatal error: init boom' in capsys.readouterr().out


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['save', 'exit'])
@patch('builtins.print')
def test_calculator_repl_save_error(mock_print, mock_input):
    with patch('app.calculator_repl.Calculator.save_history', side_effect=RuntimeError('save boom')):
        calculator_repl()
    mock_print.assert_any_call("Error saving history: save boom")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['add', '2', '3', 'history', 'undo', 'redo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_history_undo_redo_success_paths(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nCalculation History:")
    mock_print.assert_any_call("Operation undone")
    mock_print.assert_any_call("Operation redone")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['add', '2', 'cancel', 'exit'])
@patch('builtins.print')
def test_calculator_repl_cancel_second_number(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("Operation cancelled")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['load', 'exit'])
@patch('builtins.print')
def test_calculator_repl_load_error(mock_print, mock_input):
    with patch('app.calculator_repl.Calculator.load_history', side_effect=RuntimeError('load boom')):
        calculator_repl()
    mock_print.assert_any_call("Error loading history: load boom")


def test_calculator_coverage_edge_branches():
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = CalculatorConfig(base_dir=temp_path)

        with patch('app.calculator.logging.basicConfig', side_effect=RuntimeError('log boom')):
            with pytest.raises(RuntimeError, match='log boom'):
                Calculator(config=config)

        calculator = Calculator(config=config)
        calculator.config.max_history_size = 1
        calculator.set_operation(OperationFactory.create_operation('add'))
        calculator.perform_operation(1, 2)
        calculator.perform_operation(3, 4)
        assert len(calculator.history) == 1
        assert calculator.history[0].operand1 == Decimal('3')

        calculator2 = Calculator(config=config)
        calculator2.set_operation(OperationFactory.create_operation('add'))
        with patch('app.calculator.InputValidator.validate_number', side_effect=RuntimeError('bad value')):
            with pytest.raises(OperationError, match='Operation failed'):
                calculator2.perform_operation(2, 3)

        calculator3 = Calculator(config=config)
        with patch('app.calculator.pd.DataFrame.to_csv', side_effect=RuntimeError('disk fail')):
            with pytest.raises(OperationError, match='Failed to save history'):
                calculator3.save_history()

        calculator4 = Calculator(config=config)
        calculator4.clear_history()
        assert calculator4.show_history() == []
        assert calculator4.redo() is False

        with patch.object(Path, 'exists', return_value=True):
            with patch('app.calculator.pd.read_csv', side_effect=RuntimeError('read fail')):
                with pytest.raises(OperationError, match='Failed to load history'):
                    calculator4.load_history()


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_operation_error_path(mock_print, mock_input):
    with patch.object(Calculator, 'perform_operation', side_effect=OperationError('op boom')):
        calculator_repl()
    mock_print.assert_any_call("Error: op boom")


@pytest.mark.usefixtures('isolated_repl_calculator')
@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_runtime_exception_path(mock_print, mock_input):
    with patch.object(Calculator, 'perform_operation', side_effect=RuntimeError('runtime boom')):
        calculator_repl()
    mock_print.assert_any_call("Unexpected error: runtime boom")
